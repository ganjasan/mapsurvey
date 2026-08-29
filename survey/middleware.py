from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import Membership, Organization, Invitation, UserActivity


class CloudflareIPMiddleware:
    """Set request.cf_ip to the real client IP.

    On Render the app runs behind Cloudflare; the real client IP arrives in
    the CF-Connecting-IP header. REMOTE_ADDR reflects only the last hop.
    Reading the header is only safe when we know we are actually behind
    Cloudflare — otherwise an attacker can spoof it. The CLOUDFLARE_TRUSTED
    setting (default False) gates the read.

    Does NOT modify request.META["REMOTE_ADDR"] — Django internals trust
    that attribute and silent rewrites are surprising. Consumers should
    read request.cf_ip explicitly.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'CLOUDFLARE_TRUSTED', False):
            cf_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
            request.cf_ip = cf_ip or request.META.get('REMOTE_ADDR', '')
        else:
            request.cf_ip = request.META.get('REMOTE_ADDR', '')
        return self.get_response(request)


class SurveyIndexingMiddleware:
    """Apply `X-Robots-Tag: noindex` to unpublished surveys' pages.

    `survey.access_control.mark_indexing` decides; this applies. The split
    exists because the decision needs the survey and the header needs the
    response, and the two are not available in the same place: access control
    frequently returns None and lets the view build its own response, and
    `survey_header` redirects to a section or language picker.

    A header rather than a `<meta>` tag: the redirect responses render no
    template at all, and a tag would have to be added to every survey base
    template -- the same failure mode POSTHOG_EXCLUDED_PREFIXES was written to
    avoid, where a base template added later inherits whatever its author
    happened to copy.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, 'survey_noindex', False):
            response['X-Robots-Tag'] = 'noindex'
        return response


class LastActivityMiddleware:
    """Record the last time an authenticated user touched the app.

    `auth_user.last_login` only moves on explicit authentication and
    `SurveyHeader.updated_at` only on parent-survey saves, so neither reflects a
    creator quietly working under a live session. This refreshes
    `UserActivity.last_activity` on any authenticated request, throttled via the
    cache to at most one write per user per LAST_ACTIVITY_THROTTLE_SECONDS so we
    never write on every request. The write is best-effort: a failure must never
    break the request.

    Registered after AuthenticationMiddleware so request.user is populated.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.throttle = getattr(settings, 'LAST_ACTIVITY_THROTTLE_SECONDS', 300)

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            self._touch(user.id)
        return response

    def _touch(self, user_id):
        cache_key = f'last_activity_seen:{user_id}'
        try:
            # Cache-gate: if we wrote within the throttle window, skip the DB.
            # cache.add returns False when the key already exists.
            if not cache.add(cache_key, 1, self.throttle):
                return
        except Exception:
            # Cache unavailable — fall through and write (fail toward correctness).
            pass
        try:
            UserActivity.objects.update_or_create(
                user_id=user_id, defaults={'last_activity': timezone.now()},
            )
        except Exception:
            # Best-effort: never break the request over an activity write.
            pass


class ActiveOrgMiddleware:
    """
    Populate request.active_org from session['active_org_id'].
    Falls back to the user's first membership if the session value is invalid.
    Also processes pending invitation tokens stored in session.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_org = None

        if request.user.is_authenticated:
            # Process pending invitation token from session
            pending_token = request.session.pop('pending_invitation_token', None)
            if pending_token:
                self._process_pending_invitation(request, pending_token)

            org_id = request.session.get('active_org_id')
            if org_id:
                # Verify user still has membership in this org
                try:
                    membership = Membership.objects.select_related('organization').get(
                        user=request.user,
                        organization_id=org_id,
                    )
                    request.active_org = membership.organization
                except Membership.DoesNotExist:
                    # Stale session — fall through to fallback
                    org_id = None

            if not org_id:
                # Fallback: first org by join date
                membership = (
                    Membership.objects
                    .filter(user=request.user)
                    .select_related('organization')
                    .order_by('joined_at')
                    .first()
                )
                if membership:
                    request.active_org = membership.organization
                    request.session['active_org_id'] = membership.organization.id
                elif request.user.is_superuser:
                    # Superusers created via createsuperuser have no membership.
                    # Auto-assign them as owner of the first org.
                    org = Organization.objects.order_by('id').first()
                    if org:
                        membership = Membership.objects.create(
                            user=request.user, organization=org, role='owner',
                        )
                        request.active_org = org
                        request.session['active_org_id'] = org.id

        return self.get_response(request)

    def _process_pending_invitation(self, request, token):
        """Accept a pending invitation stored in the session."""
        from django.contrib import messages
        from django.utils import timezone

        try:
            invitation = Invitation.objects.select_related('organization').get(token=token)
        except Invitation.DoesNotExist:
            return

        if not invitation.is_acceptable:
            return

        Membership.objects.get_or_create(
            user=request.user,
            organization=invitation.organization,
            defaults={'role': invitation.role},
        )
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])
        request.session['active_org_id'] = invitation.organization_id
        messages.success(request, f"You've joined '{invitation.organization.name}'.")


class CreatorLanguageCookieMiddleware:
    """Mirror a creator's stored UI language into Django's language cookie.

    Why a cookie rather than reading the preference directly: `LocaleMiddleware`
    runs BEFORE `AuthenticationMiddleware` (see MIDDLEWARE order), so there is no
    `request.user` at the moment the language is resolved. Django 4.2 resolves
    from URL prefix → LANGUAGE_COOKIE_NAME → Accept-Language, and the cookie is
    the only one of those we can set from a preference.

    The DB is touched only when the cookie is ABSENT — a new browser or device —
    not on every request. Once written, the cookie carries the choice and this
    middleware costs nothing.

    Respondent pages are unaffected: they call `translation.activate()` for the
    SURVEY's language inside the view, after all middleware, so the survey's
    language always wins over the viewer's preference.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return response
        if request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            return response

        try:
            language = user.preferences.ui_language
        except Exception:
            # No preferences row, or the table is mid-migration. A missing
            # preference is not an error: Accept-Language decides instead.
            return response

        if language and language in dict(settings.LANGUAGES):
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME, language,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
            )
        return response
