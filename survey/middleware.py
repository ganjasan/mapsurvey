import logging
import re
import secrets
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

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


class EmbedSessionMiddleware(SessionMiddleware):
    """Sessions for respondents whose browser keeps no cookies in a frame (change embed-surveys).

    Safari, and every browser on iOS, blocks all third-party cookies; CHIPS
    (`Partitioned`) does not change that (verified on the PR #286 preview). A
    survey embedded on another site would lose its session on every request
    and fail CSRF on the first "Next". So under `/surveys/` the page may carry
    its own session key, three ways:

    - `X-MS-Session` request header: HTMX calls, the upload XHR, same-origin
      fetches. A cross-site page cannot make a browser send a custom header
      (that needs a CORS preflight we never grant), so it is not ambient.
    - `ms_sid` field of a urlencoded POST: the language picker and password
      gate are full-page forms. Honoured only when `Origin` is this host, so
      a foreign page cannot fixate a visitor into a key it knows.
    - `ms_h` on a GET: a one-time handoff (cache, two minutes) minted for each
      redirect this middleware rewrites, so no reusable key ever sits in a
      URL, a log line or a Referer.

    A carried session is never an authenticated one. CSRF stays fully
    enforced: the CSRF secret the page was rendered with is kept in the
    session and handed to CsrfViewMiddleware as if the cookie had arrived, so
    the token in the form is checked exactly as for everyone else. When a
    cookie did arrive, it wins and nothing here applies. Everywhere else this
    is Django's SessionMiddleware, unchanged.
    """

    HANDOFF_PREFIX = 'ms_h:'
    HANDOFF_TTL = 120
    CSRF_SESSION_KEY = '_ms_csrf_secret'
    _KEY_RE = re.compile(r'^[a-z0-9]{32}$')

    def process_request(self, request):
        super().process_request(request)
        request.ms_session_carried = False
        if not request.path.startswith('/surveys/') or settings.SESSION_COOKIE_NAME in request.COOKIES:
            return
        key = self._carried_key(request)
        if not key:
            return
        store = self.SessionStore(key)
        if not store.exists(key) or store.get('_auth_user_id'):
            return
        request.session = store
        request.ms_session_carried = True
        secret = store.get(self.CSRF_SESSION_KEY)
        if secret:
            request.COOKIES[settings.CSRF_COOKIE_NAME] = secret

    def process_response(self, request, response):
        if request.path.startswith('/surveys/') and hasattr(request, 'session'):
            from .embedding import is_framed
            carried = getattr(request, 'ms_session_carried', False)
            if carried or is_framed(request):
                self._remember_csrf_secret(request)
                key = request.session.session_key
                if key and not request.session.get('_auth_user_id'):
                    for header in ('Location', 'HX-Redirect'):
                        if response.has_header(header):
                            response[header] = self._with_handoff(request, response[header], key)
                if carried and not response.has_header('Referrer-Policy'):
                    response['Referrer-Policy'] = 'same-origin'
        return super().process_response(request, response)

    def _remember_csrf_secret(self, request):
        """Keep the CSRF secret this response was rendered with, for the carried POST that follows."""
        secret = request.META.get('CSRF_COOKIE')
        if secret and request.session.get(self.CSRF_SESSION_KEY) != secret:
            request.session[self.CSRF_SESSION_KEY] = secret

    def _carried_key(self, request):
        if request.method in ('GET', 'HEAD'):
            token = request.GET.get('ms_h')
            if token:
                cache_key = self.HANDOFF_PREFIX + token
                key = cache.get(cache_key)
                cache.delete(cache_key)
                if key:
                    return key
            key = request.headers.get('X-MS-Session', '')
        else:
            if not self._same_origin(request):
                return None
            key = request.headers.get('X-MS-Session', '')
            if not key and request.content_type == 'application/x-www-form-urlencoded':
                key = request.POST.get('ms_sid', '')
        return key if self._KEY_RE.match(key or '') else None

    @staticmethod
    def _same_origin(request):
        origin = request.headers.get('Origin', '')
        return bool(origin) and urlsplit(origin).netloc == request.get_host()

    def _with_handoff(self, request, url, key):
        resolved = urlsplit(urljoin(request.path, url))
        if (resolved.netloc and resolved.netloc != request.get_host()) or not resolved.path.startswith('/surveys/'):
            return url
        token = secrets.token_urlsafe(16)
        cache.set(self.HANDOFF_PREFIX + token, key, self.HANDOFF_TTL)
        base, hashmark, fragment = url.partition('#')
        path, _, query = base.partition('?')
        params = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k != 'ms_h']
        params.append(('ms_h', token))
        return f'{path}?{urlencode(params)}' + (hashmark + fragment if hashmark else '')


class SurveyEmbedMiddleware:
    """Let allowed sites frame a survey's respondent pages (change embed-surveys).

    `survey.access_control.mark_embeddable` decides; this applies: the
    `frame-ancestors` directive replaces `X-Frame-Options` on the responses it
    marked and nothing else changes. Sits above `XFrameOptionsMiddleware` in
    MIDDLEWARE so it sees the header that middleware added and can drop it.
    A CSP header is set here only when it is not already present: should a
    real CSP ever be introduced, that one owns the header and this becomes a
    merge, not a clobber.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        ancestors = getattr(request, 'survey_frame_ancestors', None)
        if ancestors and not response.has_header('Content-Security-Policy'):
            response['Content-Security-Policy'] = f'frame-ancestors {ancestors}'
            if response.has_header('X-Frame-Options'):
                del response['X-Frame-Options']
        return response


class PartitionedCookieMiddleware:
    """Add `Partitioned` to the session and CSRF cookies (change embed-surveys).

    A survey framed by another site only works if its cookies are sent from
    inside that frame. `SameSite=None; Secure` (set through the normal Django
    settings, see CROSS_SITE_COOKIES) is the first half; `Partitioned` (CHIPS)
    is what keeps the cookie once a browser blocks third-party cookies: the
    jar is keyed by the embedding site, so the survey keeps its session there
    without ever seeing another site's. Django has no setting for the
    attribute, and `http.cookies.Morsel` rejects unknown keys, so it rides on
    the `SameSite` value, which the Morsel writes verbatim. Only the two
    cookies, only when `Secure` -- a browser drops a `Partitioned` cookie that
    is not.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        for name in (settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME):
            morsel = response.cookies.get(name)
            if morsel is None or not morsel['secure']:
                continue
            samesite = morsel['samesite'] or ''
            if 'partitioned' not in samesite.lower():
                morsel['samesite'] = f'{samesite}; Partitioned' if samesite else 'None; Partitioned'
        return response


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


class FirstTouchMiddleware:
    """Remember a visitor's first marketing touch in a 90-day first-party cookie.

    `SignupAttribution` used to read the first touch from the session, which dies
    long before "saw us in ChatGPT, came back a week later, registered" completes;
    and at registration it fell back to the request's own referrer, i.e. the site
    itself. The cookie is written once, on the first marketing-page response that
    lacks it, and read at registration by `persist_signup_attribution`.

    Marketing pages only: respondent surfaces (/surveys/, /r/), the editor, admin
    and account pages other than the registration form never write it, so a
    respondent who later registers is attributed to the page they *started* on,
    not to the survey they answered. The value is signed, holds no identifier and
    is HttpOnly -- there is nothing in it for JavaScript to read.
    """

    EXCLUDED_PREFIXES = (
        '/surveys/', '/r/', '/editor/', '/admin/', '/static/', '/staticfiles/',
        '/media/', '/internal/', '/__debug__/', '/api/', '/i18n/',
    )
    ACCOUNTS_ALLOWED = ('/accounts/register/',)

    def __init__(self, get_response):
        self.get_response = get_response

    def _eligible(self, request):
        if request.method != 'GET':
            return False
        path = request.path
        if path.startswith('/accounts/'):
            return path in self.ACCOUNTS_ALLOWED
        return not path.startswith(self.EXCLUDED_PREFIXES)

    def __call__(self, request):
        response = self.get_response(request)
        try:
            from .events import (
                FIRST_TOUCH_COOKIE, FIRST_TOUCH_MAX_AGE, build_first_touch, encode_first_touch,
            )
            if (
                self._eligible(request)
                and FIRST_TOUCH_COOKIE not in request.COOKIES
                and 200 <= response.status_code < 300
            ):
                response.set_cookie(
                    FIRST_TOUCH_COOKIE, encode_first_touch(build_first_touch(request)),
                    max_age=FIRST_TOUCH_MAX_AGE, httponly=True, samesite='Lax',
                    secure=request.is_secure(),
                )
        except Exception:  # analytics must never break a page
            logger.debug('first-touch cookie not set', exc_info=True)
        return response
