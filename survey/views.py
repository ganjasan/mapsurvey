import re
import uuid as uuid_mod

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Q, Prefetch, Count
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import translation
from django.utils.translation import override as lang_override
from django.utils.translation import gettext as _
from .models import SurveyHeader, SurveySession, SurveySection, Answer, Question, Story, SurveyCollaborator, SurveyMapLayer
from .models import FILE_INPUT_TYPES
from .uploads import attach_upload, detach_unreferenced
from .permissions import (
    org_permission_required, survey_permission_required,
    get_effective_survey_role, get_org_membership, SURVEY_ROLE_RANK,
)
from datetime import datetime
from django import forms
from django.views.generic import UpdateView
from .forms import SurveySectionAnswerForm
from .events import (
    emit_event, build_session_start_metadata, store_utm_in_session,
    capture_signup_source, persist_signup_attribution,
)
from .acquisition import record_demo_open
from .seo_landings import (
    SEO_LANDINGS, render_seo_landing, Crumb, HOME,
    build_breadcrumb_jsonld, build_story_collection_jsonld,
)
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.core.serializers import serialize
import geojson
from django.contrib.gis.geos import GEOSGeometry
import sys
from io import BytesIO
import json
import logging
from zipfile import ZipFile
import pandas as pd

from .access_control import check_survey_access, mark_indexing
from .audit import audit
from .trash import trash_survey, restore_survey, purge_survey, purge_expired_surveys
from .versioning import resolve_version_scope
import hmac
from django.http import JsonResponse
from django.views.defaults import page_not_found
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .serialization import (
    export_survey_to_zip,
    import_survey_from_zip,
    ImportError as SerializationImportError,
    ExportError,
    EXPORT_MODES,
)
from .abuse import (
    HONEYPOT_FIELD_NAME,
    RegistrationAbuseForm,
    ResendActivationForm,
    check_registration_limit,
    client_ip,
    increment_registration_limit,
    log_abuse_event,
    verify_turnstile,
)
from .password_rules import password_checklist_rules
from django_ratelimit.core import is_ratelimited
from django.conf import settings as conf_settings
from django.http import HttpResponse

logger = logging.getLogger(__name__)


class AsyncEmailRegistrationView(
    __import__('django_registration.backends.activation.views', fromlist=['RegistrationView']).RegistrationView
):
    """Override to send activation email as HTML in a background thread."""

    email_html_template = "django_registration/activation_email.html"

    def send_activation_email(self, user):
        import threading
        from django.core.mail import send_mail as _send_mail
        from django.template.loader import render_to_string
        from django.conf import settings as conf_settings

        activation_key = self.get_activation_key(user)
        context = self.get_email_context(activation_key)
        context["user"] = user
        subject = "".join(
            render_to_string(self.email_subject_template, context, self.request).splitlines()
        )
        text_body = render_to_string(self.email_body_template, context, self.request)
        html_body = render_to_string(self.email_html_template, context, self.request)

        threading.Thread(
            target=_send_mail,
            kwargs=dict(
                subject=subject,
                message=text_body,
                from_email=conf_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_body,
            ),
            daemon=True,
        ).start()


class AbuseProtectedRegistrationView(AsyncEmailRegistrationView):
    """Registration view with three layered abuse defenses.

    Defenses fire in this order on POST:
      1. Honeypot — `website` field must be empty. Filled → silent
         fake-success redirect, no User created, no email sent.
      2. Rate limit — per-IP via django-ratelimit. The *check* runs in
         dispatch(), before form processing; the *counter* is advanced in
         post(), once form validity is known.
      3. Turnstile — siteverify token check before form save.

    The check/increment split is the correction of a shipped defect: the
    counter used to advance on every POST, so three password typos exhausted
    the 3/hour budget and locked a real person out (2026-08-17 — six POSTs,
    three 429s, no account). Validity is exactly the signal that separates a
    confused human from a bot, and it is not known until the form is
    validated. Form-invalid attempts now feed a separate, far looser counter.

    See `survey/abuse.py` for the helpers and openspec/changes/
    add-registration-abuse-defenses/ plus
    openspec/changes/registration-rate-limit-traps-humans/ for the design.
    """

    form_class = RegistrationAbuseForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["TURNSTILE_SITE_KEY"] = conf_settings.TURNSTILE_SITE_KEY
        ctx["password_rules"] = password_checklist_rules()
        return ctx

    def dispatch(self, request, *args, **kwargs):
        # Capture acquisition source when the register page is loaded directly
        # (e.g. an outreach link straight to /register/?utm_source=edu).
        if request.method == "GET":
            capture_signup_source(request)
        # Rate-limit CHECK on POST only — read-only, never advances a counter.
        # Running it here (before form processing) keeps an already-limited IP
        # from costing us a form validation or a Cloudflare round-trip. The
        # increment happens in post(), where validity is known.
        #
        # We call is_ratelimited imperatively rather than using @ratelimit so we
        # can log the AbuseEvent before responding with our own 429 instead of
        # django-ratelimit's default exception.
        #
        # Fail-open on a cache-backend outage lives in the helpers: a blind
        # limiter must not block signups. Honeypot + Turnstile still apply.
        if request.method == "POST":
            for kind in ("valid", "invalid"):
                hit = check_registration_limit(request, kind)
                if hit:
                    retry_after, detail = hit
                    log_abuse_event("ratelimit", request, detail)
                    return self.rate_limited_response(request, retry_after)
            if not conf_settings.REGISTRATION_SPLIT_RATE_LIMIT:
                # Kill switch: count every POST up front, as before this change.
                increment_registration_limit(request, "valid")
        return super().dispatch(request, *args, **kwargs)

    def rate_limited_response(self, request, retry_after):
        """Render the 429 page, keeping the machine-readable contract intact.

        Deliberately does not say which limit was hit, what the thresholds are,
        or how many attempts remain — that would let an attacker map the
        defense. It does link to sign-in and password reset, because a
        meaningful share of the people who hit this are returning users who
        forgot they already have an account.
        """
        resp = render(
            request,
            "registration/rate_limited.html",
            {"retry_after_minutes": max(1, round(retry_after / 60))},
            status=429,
        )
        resp["Retry-After"] = str(retry_after)
        return resp

    def post(self, request, *args, **kwargs):
        from django.urls import reverse

        # 1. Honeypot — checked from raw POST BEFORE form validation so a bot
        # filling the honeypot AND submitting other invalid fields still gets
        # the fake-success redirect (not a form-error 200 that fingerprints
        # the defense).
        if request.POST.get(HONEYPOT_FIELD_NAME, "").strip():
            log_abuse_event("honeypot", request, "filled")
            return redirect(reverse("django_registration_complete"))

        form = self.get_form()

        # 2. Rate-limit counter. Now — and only now — we know which bucket this
        # attempt belongs to. A form-invalid attempt is overwhelmingly a human
        # fighting the password validators, so it feeds the loose counter; a
        # well-formed one feeds the strict counter that actually gates account
        # creation. Under the kill switch dispatch() already counted it.
        if conf_settings.REGISTRATION_SPLIT_RATE_LIMIT:
            increment_registration_limit(
                request, "valid" if form.is_valid() else "invalid"
            )

        if not form.is_valid():
            return self.form_invalid(form)

        # 3. Turnstile — Cloudflare's JS widget posts as `cf-turnstile-response`.
        # A well-formed submission with a bad token is bot-shaped, and it has
        # already been counted against the strict budget above.
        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, client_ip(request)):
            detail = "missing_token" if not token else "siteverify_rejected"
            log_abuse_event("captcha", request, detail)
            form.add_error(None, "CAPTCHA verification failed. Please try again.")
            return self.form_invalid(form)

        return self.form_valid(form)

    def register(self, form):
        # django-registration creates the (inactive) user here; attach the
        # captured acquisition source. Fail-open — never blocks the signup.
        user = super().register(form)
        persist_signup_attribution(user, self.request)
        return user


class DirectActivationView(
    __import__('django_registration.backends.activation.views', fromlist=['ActivationView']).ActivationView
):
    """Activation endpoint: GET shows a confirmation page, POST activates.

    GET must stay side-effect-free. Mail-security scanners (Microsoft
    Defender Safe Links — observed in prod on 2026-07-27 with a full Chrome
    UA from Azure IPs) follow emailed links with GET minutes before the
    human clicks. When activation happened on GET, the scanner consumed the
    one inactive->active transition and the human landed on a failure page;
    two users re-registered duplicate accounts that same day. Scanners do
    not submit forms, so the POST carries the activation.

    On successful POST the user is logged in and sent straight to the
    editor. Making them re-enter credentials they typed minutes earlier was
    the measured drop-off point: 24 accounts were active but had never
    logged in. See openspec/changes/activation-confirm-post/design.md.
    """

    AUTH_BACKEND = "survey.backends.EmailOrUsernameBackend"

    def get(self, request, *args, **kwargs):
        """Validate the key and show the confirm button. Never writes."""
        from django.contrib.auth import get_user_model
        from django_registration.backends.activation.forms import ActivationForm
        from django_registration.exceptions import ActivationError

        activation_key = request.GET.get("activation_key")
        if not activation_key:
            return self.activation_failure(ActivationError("Missing activation key."))
        try:
            form = ActivationForm(data={"activation_key": activation_key})
            if not form.is_valid():
                # Expired or tampered signature — no point rendering a
                # confirm button for a dead key.
                return render(
                    request, "django_registration/activation_failed.html", {"form": form}
                )
            # Valid key. cleaned_data holds the decoded username (upstream
            # ActivationForm swaps it in after signature verification).
            User = get_user_model()
            try:
                user = User.objects.get(
                    **{User.USERNAME_FIELD: form.cleaned_data["activation_key"]}
                )
            except User.DoesNotExist:
                return render(request, "django_registration/activation_failed.html", {})
            if user.is_active:
                return self._already_active_redirect(request)
            return render(
                request,
                "django_registration/activation_confirm.html",
                {"activation_key": activation_key},
            )
        except Exception:
            return render(request, "django_registration/activation_failed.html", {})

    def post(self, request, *args, **kwargs):
        """Perform the activation the confirm form asked for, then sign in."""
        from django_registration.backends.activation.forms import ActivationForm
        from django_registration.exceptions import ActivationError

        try:
            form = ActivationForm(data={
                "activation_key": request.POST.get("activation_key", "")
            })
            if not form.is_valid():
                return render(
                    request, "django_registration/activation_failed.html", {"form": form}
                )
            try:
                activated_user = self.activate(form)
            except ActivationError as error:
                return self._activation_error_response(request, form, error)
            # Sign in only on the genuine inactive -> active transition. That
            # makes the key single-use as a credential: replaying it lands in
            # the already_activated branch, which does NOT sign anyone in.
            return self._signed_in_redirect(request, activated_user)
        except Exception:
            return render(request, "django_registration/activation_failed.html", {})

    def _already_active_redirect(self, request):
        """Route a benign repeat (scanner-style pre-visit, re-opened link) onward."""
        if request.user.is_authenticated:
            return redirect(conf_settings.LOGIN_REDIRECT_URL)
        return redirect(f"{conf_settings.LOGIN_URL}?activated=1")

    def _activation_error_response(self, request, form, error):
        """Handle ActivationError from activate().

        `already_activated` with a still-valid key is not a real failure: mail
        scanners routinely pre-fetch links, so activation may already have
        happened before the human clicked. Route them onward rather than
        dead-ending on the failure page.

        We deliberately do NOT sign them in here. Auto-login on a replayable
        key would turn the activation link into a bearer token good for the
        whole ACCOUNT_ACTIVATION_DAYS window: anyone who later obtained the
        email (forward, shared inbox, history sync) could sign in as the user.
        Activation itself is safe to auto-login because it can only ever
        succeed once. See design.md Risks.
        """
        if getattr(error, "code", None) == "already_activated":
            return self._already_active_redirect(request)
        return render(
            request,
            "django_registration/activation_failed.html",
            {"form": form, "activation_error": {
                "message": getattr(error, "message", ""),
                "code": getattr(error, "code", ""),
            }},
        )

    def _signed_in_redirect(self, request, user):
        """Log the freshly activated `user` in and redirect to the editor."""
        from django.contrib.auth import login as auth_login

        if user is None or not user.is_active:
            return render(request, "django_registration/activation_failed.html", {})
        # Explicit backend: login() normally reads user.backend, set by
        # authenticate() — which never runs on this path.
        auth_login(request, user, backend=self.AUTH_BACKEND)
        return redirect(conf_settings.LOGIN_REDIRECT_URL)

    def activation_failure(self, error):
        return render(self.request, "django_registration/activation_failed.html", {})


class ResendActivationView(AsyncEmailRegistrationView):
    """Re-send an activation email for an account that never activated.

    Subclasses the registration view purely to reuse its activation-key
    generation and threaded HTML mail sending — it never registers anyone.

    Every POST ends at the same neutral confirmation page, whatever happened:
    email sent, address unknown, account already active, honeypot filled, or
    rate limit hit. That uniformity is the anti-enumeration property, so keep
    it if you touch this. Mail goes out only for an existing INACTIVE account,
    at most RESEND_ACTIVATION_RATE_LIMIT_DAY times per address per day.

    See openspec/changes/activation-funnel-autologin/design.md (D3).
    """

    form_class = ResendActivationForm
    template_name = "django_registration/resend_activation_form.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {"form": ResendActivationForm()})

    def post(self, request, *args, **kwargs):
        from django.contrib.auth import get_user_model

        # 1. Honeypot — read raw, before validation (same rationale as
        # AbuseProtectedRegistrationView.post).
        if request.POST.get(HONEYPOT_FIELD_NAME, "").strip():
            log_abuse_event("honeypot", request, "resend_filled")
            return self._neutral_response(request)

        # 2. Rate limits. Per-IP hourly caps a single attacker; per-email daily
        # caps how much mail any one inbox can be made to receive even from
        # rotating IPs. Fail-open on cache errors, as with registration.
        limits = (
            ("resend_activation_hour",
             f"{conf_settings.RESEND_ACTIVATION_RATE_LIMIT_HOUR}/h",
             "survey.abuse.ratelimit_key", "resend_hour"),
            ("resend_activation_day",
             f"{conf_settings.RESEND_ACTIVATION_RATE_LIMIT_DAY}/d",
             "survey.abuse.ratelimit_email_key", "resend_day"),
        )
        for group, rate, key, detail in limits:
            try:
                limited = is_ratelimited(
                    request=request, group=group, fn=None,
                    key=key, rate=rate, method="POST", increment=True,
                )
            except Exception:
                limited = False
            if limited:
                log_abuse_event("ratelimit", request, detail)
                # Neutral, not 429: a 429 here would confirm to an attacker
                # that they found a real throttle worth routing around, and
                # would differ from the response an ordinary user gets.
                return self._neutral_response(request)

        form = ResendActivationForm(data=request.POST)
        if not form.is_valid():
            return self._neutral_response(request)

        email = form.cleaned_data["email"]
        User = get_user_model()
        user = User.objects.filter(email__iexact=email, is_active=False).first()
        if user is not None:
            # Keys are stateless signed values, so "re-issuing" is just signing
            # the username again — no DB write, and any older key for the same
            # account stays valid until its own expiry.
            self.send_activation_email(user)
        return self._neutral_response(request)

    def _neutral_response(self, request):
        return redirect("django_registration_resend_activation_done")


def resolve_survey(survey_slug):
    """Resolve a survey from a URL slug that may be a UUID or a name.

    Lookup order:
    1. Try parsing as UUID → lookup by SurveyHeader.uuid
       - If it hits an archived version, return the canonical survey instead
    2. Fall back to name → lookup by SurveyHeader.name (canonical only)
    3. If name matches multiple surveys → raise Http404

    Returns SurveyHeader or raises Http404.
    """
    try:
        parsed_uuid = uuid_mod.UUID(str(survey_slug))
        survey = get_object_or_404(SurveyHeader, uuid=parsed_uuid, deleted_at__isnull=True)
        # If this is an archived version, return the canonical instead
        if not survey.is_canonical and survey.canonical_survey_id:
            canonical = survey.canonical_survey
            if canonical.is_trashed:
                raise Http404
            return canonical
        return survey
    except (ValueError, AttributeError):
        pass

    surveys = SurveyHeader.objects.filter(name=survey_slug, is_canonical=True, deleted_at__isnull=True)
    count = surveys.count()
    if count == 1:
        return surveys.first()
    if count > 1:
        raise Http404
    raise Http404

def survey_not_found(request, exception=None):
	"""handler404: give respondent 404s a body, everything else Django's.

	Under `/surveys/` a 404 is usually a person following a link an organizer
	gave them -- a draft that was never published, or a survey since removed.
	Django's default page tells them nothing. This one tells them what to do
	without saying which case applies: a draft, a deleted survey and a UUID that
	names nothing all land here and produce byte-identical responses, so the
	page cannot be used to test whether a survey exists.

	`noindex` is set here too rather than left to the middleware, because
	`resolve_survey` raises before any survey is in hand and the flag would
	otherwise distinguish the draft case from the unknown-UUID one by header.
	"""
	if not request.path.startswith('/surveys/'):
		return page_not_found(request, exception)
	response = render(request, 'survey_unavailable.html', status=404)
	response['X-Robots-Tag'] = 'noindex'
	return response


def publicly_visible_surveys():
	"""Surveys an anonymous visitor may be shown or sent to.

	The landing page and the sitemap are the only two places that make this
	decision, and when they made it separately they diverged: `sitemap_xml`
	filtered on `visibility` alone and so advertised 61 drafts to search
	engines as crawlable URLs, every one of them a hard 404. Both callers go
	through here now; a third one must too.

	`status='published'` rather than the landing page's older
	`exclude(status='draft')`: `closed` and `archived` surveys answer a request
	with "this survey is closed", which is a dead end from a search result and
	was 41 of the 140 entries the sitemap used to carry. Nothing renders them
	on the landing page either -- `landing.html` has no loop over `surveys` at
	all -- so this narrows a set that reaches no template today.
	"""
	return SurveyHeader.objects.filter(
		visibility__in=['demo', 'public'],
		status='published',
		is_canonical=True,
		published_version__isnull=True,
		deleted_at__isnull=True,
	)


@lang_override('en')
def index(request):
	capture_signup_source(request)  # first-touch acquisition source for creator signups
	surveys = (
		publicly_visible_surveys()
		.select_related('organization')
		.annotate(session_count=Count('surveysession'))
		.order_by(
			models.Case(
				models.When(visibility='demo', then=0),
				models.When(is_archived=False, then=1),
				default=2,
				output_field=models.IntegerField(),
			)
		)
	)
	stories = Story.objects.filter(is_published=True).order_by('-published_date')
	return render(request, 'landing.html', {
		'surveys': surveys,
		'stories': stories,
	})

@org_permission_required('viewer')
def editor(request):
	org = request.active_org
	membership = get_org_membership(request.user, org)
	org_role = membership.role if membership else None

	# A creator whose org has no surveys has nothing to do on the dashboard —
	# and 47% of registrations never make it past that empty screen. Send them
	# straight to the thing they came to do. Viewers are exempt: they cannot
	# create, so the create page would be a dead end for them.
	if (org_role in ('owner', 'admin', 'editor')
			and request.GET.get('dashboard') != '1'
			and not SurveyHeader.objects.filter(
				organization=org, is_canonical=True, deleted_at__isnull=True,
			).exists()):
		return redirect(reverse('editor_survey_create') + '?welcome=1')

	if org_role in ('owner', 'admin'):
		# Owner/admin see all surveys in the org
		survey_list = SurveyHeader.objects.filter(organization=org)
	elif org_role == 'editor':
		# Editor sees own surveys + surveys where they are a collaborator
		collaborated_survey_ids = SurveyCollaborator.objects.filter(
			user=request.user,
		).values_list('survey_id', flat=True)
		survey_list = SurveyHeader.objects.filter(
			Q(organization=org) & (
				Q(created_by=request.user) | Q(id__in=collaborated_survey_ids)
			)
		).distinct()
	else:
		# Viewer sees all surveys (read-only)
		survey_list = SurveyHeader.objects.filter(organization=org)

	# Exclude draft copies and archived versions from dashboard
	survey_list = survey_list.filter(is_canonical=True, published_version__isnull=True)

	# Trash section: same scope, trashed only; dashboard itself hides trashed below
	trashed_surveys = list(
		survey_list.filter(deleted_at__isnull=False).order_by('-deleted_at')
	)
	survey_list = survey_list.filter(deleted_at__isnull=True)

	# Prefetch archived versions for version-aware download dropdown
	archived_versions_prefetch = Prefetch(
		'versions',
		queryset=SurveyHeader.objects.filter(is_canonical=False).order_by('-version_number'),
		to_attr='prefetched_archived_versions',
	)
	survey_list = survey_list.prefetch_related(archived_versions_prefetch)

	show_archived = request.GET.get('show_archived') == '1'
	if not show_archived:
		survey_list = survey_list.exclude(status='archived')

	# Reverse OneToOne used by the "Results live" card chip — avoid N+1
	survey_list = survey_list.select_related('public_results_page')

	# Session counts span the whole version family: publish_draft() moves
	# sessions onto archived headers, so a per-header Count would collapse to
	# ~0 right after publishing. One grouped query over all families.
	survey_list = list(survey_list)
	from django.db.models.functions import Coalesce
	family_counts = dict(
		SurveySession.objects
		.filter(
			Q(survey__in=[s.id for s in survey_list])
			| Q(survey__canonical_survey_id__in=[s.id for s in survey_list])
		)
		.annotate(fam=Coalesce('survey__canonical_survey_id', 'survey_id'))
		.values('fam')
		.annotate(n=Count('id'))
		.values_list('fam', 'n')
	)

	# Compute completion KPIs per survey (family-wide via the service scope)
	from .analytics import SurveyAnalyticsService
	surveys_with_kpi = []
	for survey in survey_list:
		survey.session_count = family_counts.get(survey.id, 0)
		overview = SurveyAnalyticsService(survey).get_overview()
		survey.completed_count = overview['completed_count']
		survey.completion_rate = overview['completion_rate']
		surveys_with_kpi.append(survey)

	context = {
		"survey_headers": surveys_with_kpi,
		"org_role": org_role,
		"show_archived": show_archived,
		"trashed_surveys": trashed_surveys,
	}
	return render(request, "editor.html", context)


# ISO 639-1 language names in their native form
LANGUAGE_NAMES = {
	'en': 'English',
	'ru': 'Русский',
	'ky': 'Кыргызча',
	'uz': "O'zbekcha",
	'tg': 'Тоҷикӣ',
	'kk': 'Қазақша',
	'de': 'Deutsch',
	'fr': 'Français',
	'es': 'Español',
	'it': 'Italiano',
	'pt': 'Português',
	'zh': '中文',
	'ja': '日本語',
	'ko': '한국어',
	'ar': 'العربية',
	'hi': 'हिन्दी',
	'pl': 'Polski',
	'uk': 'Українська',
	'nl': 'Nederlands',
	'sv': 'Svenska',
	'fi': 'Suomi',
	'no': 'Norsk',
	'da': 'Dansk',
	'cs': 'Čeština',
	'tr': 'Türkçe',
	'he': 'עברית',
	'th': 'ไทย',
	'vi': 'Tiếng Việt',
	'az': 'Azərbaycanca',
	'ka': 'ქართული',
	'hy': 'Հայերdelays',
	'mn': 'Монгол',
}


def survey_language_select(request, survey_slug):
	"""Display language selection screen for multilingual surveys."""
	survey = resolve_survey(survey_slug)

	# Capture UTM params on GET (before language choice redirect)
	if request.method == 'GET':
		store_utm_in_session(request)

	access_response = check_survey_access(request, survey)
	if access_response is not None:
		return access_response

	if not survey.is_multilingual():
		# Single-language survey - redirect directly to first section
		return redirect('survey', survey_slug=str(survey.uuid))

	if request.method == 'POST':
		selected_language = request.POST.get('language')
		if selected_language and selected_language in survey.available_languages:
			# Activate Django i18n language. Deliberately NOT written to a
			# site-wide Django language key: since Django 4.0 the session is not
			# consulted at all (`get_language_from_request` reads URL prefix,
			# LANGUAGE_COOKIE_NAME, then Accept-Language), so the old
			# `session['_language']` write did nothing -- and once a real
			# language cookie exists for creators, a respondent picking a survey
			# language must not reach across and re-language the editor.
			# `session['survey_language']` below is ours and IS read, further down.
			translation.activate(selected_language)

			# Create or update survey session with selected language
			if request.session.get('survey_session_id'):
				del request.session['survey_session_id']

			survey_session = SurveySession(survey=survey, language=selected_language)
			survey_session.save()
			request.session['survey_session_id'] = survey_session.id
			request.session['survey_language'] = selected_language
			emit_event(survey_session, 'session_start', build_session_start_metadata(request))
			record_demo_open(survey_session, request)

			# Redirect to first section
			start_section = survey.start_section()
			if start_section:
				return redirect('section', survey_slug=str(survey.uuid), section_name=start_section.name)
			return redirect(survey.redirect_url)

	# Build language list with native names
	languages = []
	for lang_code in survey.available_languages:
		languages.append({
			'code': lang_code,
			'name': LANGUAGE_NAMES.get(lang_code, lang_code)
		})

	context = {
		'survey': survey,
		'languages': languages,
	}
	return render(request, 'survey_language_select.html', context)


def survey_header(request, survey_slug):
	if request.session.get('survey_session_id'):
		del request.session['survey_session_id']
	if request.session.get('survey_language'):
		del request.session['survey_language']
	request.session.pop('utm_params', None)

	survey = resolve_survey(survey_slug)

	# Capture UTM params before redirect (they'd be lost otherwise)
	store_utm_in_session(request)

	access_response = check_survey_access(request, survey)
	if access_response is not None:
		return access_response

	# Redirect to language selection for multilingual surveys
	if survey.is_multilingual():
		return redirect('survey_language_select', survey_slug=str(survey.uuid))

	start_section = survey.start_section()
	slug = str(survey.uuid)
	redirect_page = ("../" + slug + "/" + start_section.name) if start_section else survey.redirect_url

	return HttpResponseRedirect(redirect_page)
	
	#context = {'survey': survey, 'section': survey.start_section()}

	#return render(request, 'survey_header.html', context)


def _session_visibility(session_survey, survey_session_id):
	"""Visibility map for a session's current stored answers."""
	from .visibility import compute_visibility, answers_by_code_for_session
	session = SurveySession.objects.filter(pk=survey_session_id).first()
	answers = answers_by_code_for_session(session) if session else {}
	return compute_visibility(session_survey, answers)


def _visible_chain_position(vmap, section):
	"""(section_current, section_total) over the visible chain; None if hidden."""
	chain_ids = [s.id for s in vmap.visible_sections]
	if section.id not in chain_ids:
		return None, len(chain_ids)
	return chain_ids.index(section.id) + 1, len(chain_ids)


def _build_section_context(request, survey, session_survey, section, selected_language, section_current, section_total, vmap=None):
	"""Build template context for a survey section (used by both GET and POST→next)."""
	if vmap is None:
		vmap = _session_visibility(session_survey, request.session.get('survey_session_id'))

	# Questions conditioned on a controller in THIS section stay in the DOM (the
	# client shows/hides them live); questions hidden by anything else — an
	# earlier section's answer, a hidden controller — are excluded server-side
	# and materialise on the next render if answers change (design D5).
	all_questions = list(section.questions())
	same_section_codes = {q.code for q in all_questions}
	client_rules = {}
	questions = []
	for q in all_questions:
		rule = q.visibility_rule if isinstance(q.visibility_rule, dict) else None
		same_section_rule = bool(rule) and rule.get('question_code') in same_section_codes
		if same_section_rule and ('question', q.id) not in vmap.broken:
			client_rules[q.code] = {
				'question_code': rule.get('question_code'),
				'choice_codes': [c for c in (rule.get('choice_codes') or [])],
			}
			questions.append(q)
		elif vmap.is_question_visible(q.id):
			questions.append(q)

	# Query existing answers for this session and section
	existing_answers = Answer.objects.filter(
		survey_session_id=request.session['survey_session_id'],
		question__in=questions,
		parent_answer_id__isnull=True,
	).select_related('question')

	# Build initial dict for scalar fields and geo GeoJSON for geo fields
	initial = {}
	existing_geo_answers = {}
	answers_by_question = {}
	for answer in existing_answers:
		q = answer.question
		answers_by_question.setdefault(q.code, []).append(answer)

	for question in questions:
		q_answers = answers_by_question.get(question.code, [])
		if not q_answers:
			continue

		if question.input_type in ('point', 'line', 'polygon'):
			features = []
			for answer in q_answers:
				geometry = getattr(answer, question.input_type)
				if geometry is None:
					continue
				feature = {
					'type': 'Feature',
					'geometry': json.loads(geometry.geojson),
					'properties': {'question_id': question.code},
				}
				child_answers = Answer.objects.filter(parent_answer_id=answer).select_related('question')
				for child in child_answers:
					sub_q = child.question
					if child.upload_id:
						# The token round-trips: the popup widget resolves it
						# back to the uploaded state on revisit.
						feature['properties'][sub_q.code] = [str(child.upload_id)]
					elif child.text is not None:
						feature['properties'][sub_q.code] = [child.text]
					elif child.numeric is not None:
						feature['properties'][sub_q.code] = [str(child.numeric)]
					elif child.selected_choices:
						feature['properties'][sub_q.code] = [str(c) for c in child.selected_choices]
				features.append(feature)
			if features:
				existing_geo_answers[question.code] = features
		else:
			answer = q_answers[0]
			if question.input_type in ('text', 'text_line', 'datetime'):
				if answer.text is not None:
					initial[question.code] = answer.text
			elif question.input_type == 'number':
				if answer.numeric is not None:
					initial[question.code] = answer.numeric
			elif question.input_type in ('choice', 'rating'):
				if answer.selected_choices:
					initial[question.code] = str(answer.selected_choices[0])
				elif answer.numeric is not None:
					initial[question.code] = str(int(answer.numeric))
			elif question.input_type == 'multichoice':
				if answer.selected_choices:
					initial[question.code] = [str(c) for c in answer.selected_choices]
			elif question.input_type == 'ranking':
				# Order matters here, unlike multichoice: this list is the answer.
				if answer.selected_choices:
					initial[question.code] = [str(c) for c in answer.selected_choices]
			elif question.input_type in FILE_INPUT_TYPES:
				# All tokens for the question; the widget resolves each to the
				# uploaded state (thumbnail + signed link) at render time.
				tokens = [str(x.upload_id) for x in q_answers if x.upload_id]
				if tokens:
					initial[question.code] = tokens
			elif question.input_type == 'range':
				if answer.numeric is not None:
					# The slider takes an int; the choice-based styles are radios
					# and need the string form to match one of their choices.
					# Same stored value either way — only the shape differs.
					resolved_style = SurveySectionAnswerForm.resolve_display_style(
						question, section.survey_header.get_default_rating_display_style()
					)
					if resolved_style in SurveySectionAnswerForm.CHOICE_BASED_STYLES:
						initial[question.code] = str(int(answer.numeric))
					else:
						initial[question.code] = int(answer.numeric)

	form = SurveySectionAnswerForm(initial=initial, section=section, question=None, survey_session_id=request.session['survey_session_id'], language=selected_language, questions_override=questions)

	subquestions_forms = {}
	for question in questions:
		subquestions_forms[question.code] = SurveySectionAnswerForm(initial={}, section=section, question=question, survey_session_id=request.session['survey_session_id'], language=selected_language).as_p()

	section_title = section.get_translated_title(selected_language)
	section_subheading = section.get_translated_subheading(selected_language)

	return {
		'form': form,
		'subquestions_forms': subquestions_forms,
		'existing_geo_answers': existing_geo_answers,
		'survey': survey,
		'section': section,
		'section_title': section_title,
		'section_subheading': section_subheading,
		'selected_language': selected_language,
		'section_current': section_current,
		'section_total': section_total,
		'hidden_layers_json': json.dumps([i for i in (section.hidden_layers or []) if isinstance(i, int)]),
		'visibility_rules_json': json.dumps(client_rules),
	}


def _build_map_layers_metadata(survey):
	"""Layer list for the respondent shell — config only, geometry stays behind
	the gated endpoint. Empty when the kill switch is off."""
	from django.conf import settings as django_settings
	if not django_settings.MAP_REFERENCE_LAYERS:
		return []
	return [
		{
			'id': layer.pk,
			'name': layer.name,
			'color': layer.color,
			'label_field': layer.label_field,
			'show_popups': layer.show_popups,
			'url': reverse('survey_layer_geojson', kwargs={
				'survey_slug': str(survey.uuid), 'layer_id': layer.pk,
			}),
		}
		for layer in survey.map_layers.all()
	]


def survey_section(request, survey_slug, section_name):

	survey = resolve_survey(survey_slug)

	access_response = check_survey_access(request, survey)
	if access_response is not None:
		return access_response

	# For multilingual surveys, redirect to language selection if no language chosen
	if survey.is_multilingual() and not request.session.get('survey_language'):
		return redirect('survey_language_select', survey_slug=str(survey.uuid))

	# Get selected language. A single-language survey never shows the language
	# picker, so default to its one language (otherwise content would fall back).
	selected_language = request.session.get('survey_language')
	if not selected_language and survey.available_languages:
		selected_language = survey.available_languages[0]
		request.session['survey_language'] = selected_language

	# Activate Django i18n so {% trans %} renders in the selected language
	if selected_language:
		translation.activate(selected_language)

	# The session cookie is one site-wide value, so it may name a session from a
	# *different* survey (respondent moved between surveys via direct section
	# links — the entry view that clears it is easy to bypass), a session the
	# creator soft-deleted, or a hard-deleted row. Honour it only when the
	# session is usable for this survey; anything else falls back to the
	# first-visit path. Trusting it blindly made the section lookup below raise
	# an unhandled DoesNotExist — a 500 on a respondent URL.
	survey_session = None
	cookie_session_id = request.session.get('survey_session_id')
	if cookie_session_id:
		candidate = SurveySession.objects.select_related('survey').filter(pk=cookie_session_id).first()
		if candidate is not None and not candidate.is_deleted and (
			candidate.survey_id == survey.id
			or candidate.survey.canonical_survey_id == survey.id
		):
			survey_session = candidate
	if survey_session is None:
		survey_session = SurveySession(survey=survey, language=selected_language)
		survey_session.save()
		request.session['survey_session_id'] = survey_session.id
		emit_event(survey_session, 'session_start', build_session_start_metadata(request))
		record_demo_open(survey_session, request)

	# Version routing: use the session's survey for section lookup
	# (may be an archived version if respondent started before a new version was published)
	session_survey = survey_session.survey

	section = SurveySection.objects.filter(survey_header=session_survey, name=section_name).first()
	if section is None:
		# A stale or hand-edited link — the session is already scoped to this
		# survey, so the name simply doesn't exist here. Restart at the entry
		# point (which resolves the real head section) instead of a 500.
		request.session.pop('survey_session_id', None)
		return redirect('survey', survey_slug=str(survey.uuid))

	# Visibility for this session's stored answers; progress counts the visible
	# chain only (kill switch off → the chain is the full linked list).
	vmap = _session_visibility(session_survey, survey_session.id)

	# A hidden section must not render, even by direct URL — same exit as an
	# unknown section name, but the session survives (only the URL was wrong).
	if request.method != 'POST' and not vmap.is_section_visible(section.id):
		return redirect('survey', survey_slug=str(survey.uuid))

	section_current, section_total = _visible_chain_position(vmap, section)
	if section_current is None:
		# POST to a hidden section (stale tab): treat like the direct-URL case.
		return redirect('survey', survey_slug=str(survey.uuid))

	if request.method == 'POST':
		form = SurveySectionAnswerForm(initial=request.POST, section=section, question=None, survey_session_id=request.session['survey_session_id'], language=selected_language)

		#save data to answers
		section_questions = section.questions()
		survey_session = SurveySession.objects.get(pk=request.session['survey_session_id'])

		# Visibility under the SUBMITTED state: stored answers overlaid with the
		# controller values in this POST. A value posted for a question hidden
		# under this state (stale DOM, back-navigation, tampering) is discarded
		# below — the server never trusts the client's idea of what was visible.
		from .visibility import compute_visibility, answers_by_code_for_session, CONTROLLER_TYPES
		submitted_answers = answers_by_code_for_session(survey_session)
		for q in section_questions:
			if q.input_type in CONTROLLER_TYPES:
				posted = [int(v) for v in request.POST.getlist(q.code) if v != '']
				if posted:
					submitted_answers[q.code] = posted
				else:
					submitted_answers.pop(q.code, None)
		vmap_post = compute_visibility(session_survey, submitted_answers)

		# Delete existing answers for this session and section before saving new ones
		section_question_ids = [q.id for q in section_questions]
		Answer.objects.filter(
			survey_session=survey_session,
			question_id__in=section_question_ids,
			parent_answer_id__isnull=True,
		).delete()

		for question in section_questions:
			if not vmap_post.is_question_visible(question.id):
				continue
			result = request.POST.getlist(question.code)
			# An unanswered control still posts its name with an empty value —
			# the dropdown's placeholder option is the case that surfaced this.
			# Without the filter a blank ride-along becomes a stored answer.
			result = [v for v in result if v != '']

			if (result != []):
				# Storage dispatches on input_type ONLY. It used to branch on
				# whether `choices` was non-empty first, so a stale choices list
				# left over from a type switch routed a point question's GeoJSON
				# into int() — an unhandled 500 on every submit of the section.
				if question.input_type in ('point', 'line', 'polygon'):
					geostr_list = [g for g in result[0].split('|') if g != '']
					# The UI enforces max_features; this clamp only keeps a
					# tampered or scripted POST within bounds. The section
					# POST has no error-render path (required is client-side
					# too), so excess features are discarded, not rejected.
					max_features = (question.validation_settings or {}).get('max_features')
					if isinstance(max_features, int) and max_features > 0:
						geostr_list = geostr_list[:max_features]
					for geostr in geostr_list:
						if geostr != '':
							answer = Answer(survey_session=survey_session, question=question)

							gj = geojson.loads(geostr)
							geometry = geojson.dumps(gj['geometry'])
							resultToSave = GEOSGeometry(geometry)

							if question.input_type == "point":
								answer.point = resultToSave
							elif question.input_type == "line":
								answer.line = resultToSave
							elif question.input_type == "polygon":
								answer.polygon = resultToSave

							answer.save()

							#сохранить properties как ответы наследники
							properties = gj['properties'];
							for key, value in properties.items():
								if key != 'question_id':
									sub_question = Question.objects.get(Q(survey_section=section) & Q(code=key))
									sub_answer = Answer(survey_session=survey_session, question=sub_question, parent_answer_id = answer)
									first = value[0] if value else None
									if sub_question.input_type in ('text', 'text_line', 'datetime'):
										if first:
											sub_answer.text = first
									elif sub_question.input_type in ('number', 'range'):
										if first:
											sub_answer.numeric = float(first)
									elif sub_question.input_type in ('choice', 'multichoice', 'rating'):
										sub_answer.selected_choices = [int(v) for v in value if v]
									elif sub_question.input_type in FILE_INPUT_TYPES:
										# The popup carries async-upload tokens as ordinary
										# property values — one per file. Each becomes its
										# own child Answer; foreign or stale tokens skip
										# their answer, never the feature.
										from .uploads import max_files_for as _mff
										for token in [v for v in value if v][:_mff(sub_question)]:
											upload = attach_upload(survey_session, sub_question, token)
											if upload is None:
												continue
											extra = Answer(survey_session=survey_session,
											               question=sub_question,
											               parent_answer_id=answer,
											               upload=upload)
											extra.save()
										continue
									sub_answer.save()

				elif question.input_type in ('text', 'text_line', 'datetime'):
					# datetime keeps its raw datetime-local string; that is the
					# form prepopulation and analytics read back from `text`.
					answer = Answer(survey_session=survey_session, question=question)
					answer.text = result[0]
					answer.save()

				elif question.input_type in ('number', 'range'):
					answer = Answer(survey_session=survey_session, question=question)
					if result[0]:
						answer.numeric = float(result[0])
					answer.save()

				elif question.input_type == 'ranking':
					# The submitted order is the DOM order of the widget's hidden
					# inputs. Store it only when it is a permutation of the
					# question's items: every item exactly once, nothing else.
					# An invalid ranking cannot be produced by the widget, so it
					# is tampering or a bug — stored as nothing, the way an
					# unanswered question is, rather than as a half-order.
					submitted = [r for r in result if r != '']
					defined = [str(c["code"]) for c in (question.choices or [])]
					if sorted(submitted) == sorted(defined) and defined:
						answer = Answer(survey_session=survey_session, question=question)
						answer.selected_choices = [int(r) for r in submitted]
						answer.save()

				elif question.input_type in ('choice', 'multichoice', 'rating'):
					answer = Answer(survey_session=survey_session, question=question)
					answer.selected_choices = [int(r) for r in result if r]
					answer.save()

				elif question.input_type in FILE_INPUT_TYPES:
					# The form posts async-upload tokens, never bytes — one
					# hidden input per file, several files per question. Tokens
					# that are not this session's for this question are skipped;
					# the creator's per-question cap clamps the rest, like
					# max_features does for geo.
					from .uploads import max_files_for
					for token in result[:max_files_for(question)]:
						upload = attach_upload(survey_session, question, token)
						if upload is not None:
							answer = Answer(survey_session=survey_session, question=question)
							answer.upload = upload
							answer.save()

				# html/image collect nothing; any other type stores nothing.

		# A replaced or dropped file: its upload no longer has an Answer after the
		# rewrite above, so it goes back to attached=False for orphan reclamation.
		detach_unreferenced(survey_session, section_question_ids)

		# Abandoned-branch cleanup: with the new answers stored, purge answers to
		# questions now hidden anywhere in the survey (changing "Area 7" to
		# "Area 4" removes what was collected inside the Area 7 section). Geo
		# parents cascade to their sub-answers.
		vmap_final = compute_visibility(session_survey, answers_by_code_for_session(survey_session))
		hidden_question_ids = [qid for qid, visible in vmap_final.question_visible.items() if not visible]
		if hidden_question_ids:
			Answer.objects.filter(
				survey_session=survey_session,
				question_id__in=hidden_question_ids,
				parent_answer_id__isnull=True,
			).delete()

		emit_event(survey_session, 'section_submit', {
			'section_name': section.name, 'section_index': section_current,
		})

		# Navigation walks the visible chain under the just-saved answers.
		chain = vmap_final.visible_sections
		chain_ids = [s.id for s in chain]
		if section.id in chain_ids:
			pos = chain_ids.index(section.id)
		else:
			# The just-submitted section went hidden (its own controller changed
			# on this very submit). Fall back to the nearest visible ancestor.
			pos = 0
			s = section
			while s.prev_section:
				s = s.prev_section
				if s.id in chain_ids:
					pos = chain_ids.index(s.id)
					break
		next_visible = chain[pos + 1] if pos + 1 < len(chain) else None
		prev_visible = chain[pos - 1] if pos > 0 else None
		section_total = len(chain)

		nav_direction = request.POST.get('nav_direction', 'forward')
		is_htmx = request.headers.get('HX-Request') == 'true'

		if is_htmx:
			if nav_direction == 'back' and prev_visible:
				prev_current = chain_ids.index(prev_visible.id) + 1
				# HTMX swaps the partial without a GET, so emit the view here —
				# otherwise only the head section (initial GET) ever records a view.
				emit_event(survey_session, 'section_view', {
					'section_name': prev_visible.name, 'section_index': prev_current,
				})
				prev_ctx = _build_section_context(request, survey, session_survey, prev_visible, selected_language, prev_current, section_total, vmap=vmap_final)
				return render(request, 'partials/survey_section_partial.html', prev_ctx)

			if next_visible:
				next_current = chain_ids.index(next_visible.id) + 1
				# HTMX swaps the partial without a GET — emit the view for the
				# section actually shown, so downstream sections aren't stuck at 0 views.
				emit_event(survey_session, 'section_view', {
					'section_name': next_visible.name, 'section_index': next_current,
				})
				next_ctx = _build_section_context(request, survey, session_survey, next_visible, selected_language, next_current, section_total, vmap=vmap_final)
				return render(request, 'partials/survey_section_partial.html', next_ctx)
			else:
				if survey.redirect_url == "#":
					redirect_target = reverse('survey_thanks', args=[str(survey.uuid)])
				else:
					redirect_target = survey.redirect_url
				response = HttpResponse()
				response['HX-Redirect'] = redirect_target
				return response

		if nav_direction == 'back' and prev_visible:
			return HttpResponseRedirect("../" + prev_visible.name)

		if next_visible:
			next_page = "../" + next_visible.name
		elif survey.redirect_url == "#":
			next_page = reverse('survey_thanks', args=[str(survey.uuid)])
		else:
			next_page = survey.redirect_url
		return HttpResponseRedirect(next_page)

	else:
		is_htmx = request.headers.get('HX-Request') == 'true'

		# Emit section_view event
		try:
			_sess = SurveySession.objects.get(pk=request.session['survey_session_id'])
			emit_event(_sess, 'section_view', {
				'section_name': section.name, 'section_index': section_current,
			})
		except SurveySession.DoesNotExist:
			pass

		ctx = _build_section_context(request, survey, session_survey, section, selected_language, section_current, section_total, vmap=vmap)

		if is_htmx:
			return render(request, 'partials/survey_section_partial.html', ctx)

		# Full page render — add initial map state for the shell
		head_section = section
		# Walk back to head for initial map state
		while head_section.prev_section:
			head_section = head_section.prev_section

		# Survey-level defaults take priority, then head section, then Berlin fallback
		if survey.start_map_postion:
			ctx['initial_map_lat'] = survey.start_map_postion.y
			ctx['initial_map_lng'] = survey.start_map_postion.x
		elif head_section.start_map_postion:
			ctx['initial_map_lat'] = head_section.start_map_postion.y
			ctx['initial_map_lng'] = head_section.start_map_postion.x
		else:
			ctx['initial_map_lat'] = 52.52
			ctx['initial_map_lng'] = 13.405

		if survey.start_map_zoom is not None:
			ctx['initial_map_zoom'] = survey.start_map_zoom
		elif head_section.start_map_zoom is not None:
			ctx['initial_map_zoom'] = head_section.start_map_zoom
		else:
			ctx['initial_map_zoom'] = 12

		ctx['initial_use_geolocation'] = survey.use_geolocation
		ctx['map_layers'] = _build_map_layers_metadata(survey)

		return render(request, 'survey_section.html', ctx)

def _get_version_surveys(survey, version_param):
	"""Resolve which survey(s) to export based on version parameter.

	Returns list of (survey, prefix) tuples. The prefix is empty when the scope
	is a single version, so a single-version survey keeps unprefixed filenames
	whatever the parameter says.

	The parameter itself is parsed by versioning.resolve_version_scope — the
	same call the analytics dashboard makes, so both surfaces answer the same
	question for the same URL.
	"""
	scope = resolve_version_scope(survey, version_param)
	if scope.is_family:
		return [(header, f'v{header.version_number}_') for header in scope.headers]
	return [(header, '') for header in scope.headers]


@login_required
def download_data(request, survey_slug):
	in_memory = BytesIO()
	zip = ZipFile(in_memory, "a")

	survey = resolve_survey(survey_slug)

	# Authorization, not just authentication: this export carries respondent
	# geometry and free text, so being signed in is not enough -- the caller needs
	# a role on this survey. `survey_permission_required` cannot be used here
	# because it looks the survey up by UUID, and this route accepts a name too.
	#
	# Every denial is a 404, including "no role" and "wrong org". A 403 would
	# confirm that a UUID names a real survey, which is exactly the fact the
	# removed public listing used to hand out.
	role = get_effective_survey_role(request.user, survey)
	if SURVEY_ROLE_RANK.get(role, -1) < SURVEY_ROLE_RANK['viewer']:
		logger.warning(
			"Denied survey export: user=%s survey=%s role=%s",
			request.user.pk, survey.uuid, role,
		)
		raise Http404

	# Checked once, on the survey the URL names, before the family is expanded:
	# a SurveyCollaborator holds a row on the canonical survey, not on each
	# archived version header, so re-checking per version would deny them their
	# own history.
	version_param = request.GET.get('version')
	version_surveys = _get_version_surveys(survey, version_param)

	include_all = request.GET.get('include_all') == '1'

	# Pre-compute excluded session IDs (trashed + not_approved)
	excluded_session_ids = set()
	if not include_all:
		for target_survey, _ in version_surveys:
			excluded_session_ids |= set(
				SurveySession.objects
				.filter(survey=target_survey)
				.filter(
					Q(is_deleted=True) | Q(validation_status='not_approved')
				)
				.values_list('id', flat=True)
			)

	for target_survey, prefix in version_surveys:
		_export_survey_data(zip, target_survey, prefix, excluded_session_ids)

	#Windows bug fix
	for file in zip.filelist:
		file.create_system = 0

	zip.close()
	response = HttpResponse(content_type="application/zip")
	response["Content-Disposition"] = "attachment; filename={filename}.zip".format(filename=_sanitize_filename(survey.name))

	in_memory.seek(0)
	response.write(in_memory.read())

	return response


def _sanitize_filename(name):
	"""Remove characters that are invalid in Windows filenames."""
	return re.sub(r'[<>:"/\\|?*]', '_', name)


# Every input type is classified for export. A type in none of these sets is a
# bug — it means INPUT_TYPE_CHOICES gained a member and nobody decided how it
# leaves the platform — so _answer_cell warns rather than dropping it silently,
# which is how datetime went missing from the download unnoticed.

# Carry respondent input; exported as a CSV column or a GeoJSON property.
EXPORT_VALUE_TYPES = frozenset({
	'text', 'text_line', 'number', 'range',
	'choice', 'rating', 'multichoice', 'datetime', 'ranking',
	'photo', 'audio', 'document',
})


def _upload_archive_path(question, answer):
	"""Where a file answer lives inside the responses ZIP. The same string is
	the CSV/GeoJSON cell, so a row names the file sitting next to it."""
	return 'files/{sid}/{code}__{name}'.format(
		sid=answer.survey_session_id,
		code=question.code,
		name=_sanitize_filename(answer.upload.original_name),
	)

# Exported as GeoJSON layers in their own right, never as a cell.
EXPORT_GEOMETRY_TYPES = frozenset({'point', 'line', 'polygon'})

# Presentational; they collect nothing, so there is nothing to export.
EXPORT_DISPLAY_ONLY_TYPES = frozenset({'image', 'html'})

# Returned by _answer_cell for questions that must not produce a column at all,
# which is distinct from a question that produces an empty one.
EXPORT_NO_COLUMN = object()


def _format_datetime_cell(raw):
	"""Serialise a stored datetime answer as ISO 8601.

	Values that do not parse are passed through unchanged: a raw string the
	creator can still interpret beats a blank cell.
	"""
	if not raw:
		return ""
	try:
		return datetime.fromisoformat(raw).isoformat()
	except (TypeError, ValueError):
		return raw


def _answer_cell(question, answers):
	"""Format one question's answer for export.

	`answers` holds the rows belonging to this question and nothing else, which
	is what keeps a blank question from inheriting its neighbour's value: the
	result is computed per call rather than accumulated across a loop.

	Returns EXPORT_NO_COLUMN for questions that should not appear as a cell.
	"""
	input_type = question.input_type

	if input_type in EXPORT_GEOMETRY_TYPES or input_type in EXPORT_DISPLAY_ONLY_TYPES:
		return EXPORT_NO_COLUMN

	if input_type not in EXPORT_VALUE_TYPES:
		logger.warning(
			"Export: question %s has unclassified input_type %r; exporting an "
			"empty column. Classify it in survey/views.py.",
			question.code, input_type,
		)
		return ""

	if not answers:
		return ""

	answer = answers[0]

	if input_type in ('photo', 'audio', 'document'):
		# Several files per question: the cell names every archive path. The
		# geo sub-answer path hands all rows in at once; the CSV loop passes
		# one at a time and concatenates in the caller — same separator.
		paths = [_upload_archive_path(question, a) for a in answers if a.upload_id]
		return '; '.join(paths)

	if input_type in ('text', 'text_line'):
		return answer.text if answer.text is not None else ""

	if input_type == 'datetime':
		return _format_datetime_cell(answer.text)

	if input_type in ('number', 'range'):
		if answer.numeric is not None:
			return answer.numeric
		if answer.selected_choices:
			return answer.selected_choices[0]
		return ""

	if input_type in ('choice', 'rating'):
		names = answer.get_selected_choice_names()
		return names[0] if names else ""

	if input_type == 'multichoice':
		return "; ".join(answer.get_selected_choice_names())

	if input_type == 'ranking':
		# One column per item, valued by its rank: a single "a > b > c" cell
		# reads well and analyses badly, and ranks are what the creator wants
		# to average.
		ranks = {}
		for position, code in enumerate(answer.selected_choices or [], start=1):
			ranks[f"{question.name}: {question.get_choice_name(code)}"] = position
		return ranks

	return ""


def _export_survey_data(zip, survey, prefix='', excluded_session_ids=None):
	"""Export a single survey's data into the zip with optional filename prefix.

	Args:
		excluded_session_ids: set of session PKs to skip (trashed + not_approved).
			Empty set or None means export all.
	"""
	if excluded_session_ids is None:
		excluded_session_ids = set()

	from .models import FILE_INPUT_TYPES as _FILE_TYPES

	#обработка гео вопросов
	geo_questions = survey.geo_questions()

	for question in geo_questions:

		layer_properties = {
			"survey": question.survey_section.survey_header.name,
			"survey_section": question.survey_section.name,
			"required": question.required,
		}

		#получить ответы
		features = []
		answers = question.answers()
		for geo_answer in answers:
			# Skip excluded sessions
			if geo_answer.survey_session_id in excluded_session_ids:
				continue

			#получить геометрию
			geo_type = question.input_type
			if geo_type == "polygon":
				coordinates =  [[[i[0],i[1]] for i in geo_answer.polygon.coords[0]]]
				geometry_type = "Polygon"
			elif geo_type == "line":
				coordinates =  [[i[0],i[1]] for i in geo_answer.line.coords]
				geometry_type = "LineString"
			elif geo_type == "point":
				coordinates =  [geo_answer.point.coords[0], geo_answer.point.coords[1]]
				geometry_type = "Point"

			#получить properties из subquestions
			properties = {}
			subanswers = geo_answer.subAnswers()
			for subquestion, rows in subanswers.items():
				cell = _answer_cell(subquestion, rows)
				# Unlike the CSV, every sub-question keeps a property even when
				# it holds nothing: a feature collection whose attribute set
				# varies per feature is awkward to read in QGIS.
				properties[subquestion.name] = "" if cell is EXPORT_NO_COLUMN else cell

			properties["session"] = str(geo_answer.survey_session)
			properties["session_id"] = geo_answer.survey_session_id
			properties["language"] = geo_answer.survey_session.language or ''
			properties["validation_status"] = geo_answer.survey_session.validation_status or ''

			feature = {
				"type": "Feature",
				"properties": properties,
				"geometry":{
					"type": geometry_type,
					"coordinates": coordinates,
				}
			}

			features.append(feature)

		geojson_dict = {
			"type": "FeatureCollection",
			"name": question.name,
			"crs": {"type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" }},
			"properties": layer_properties,
			"features": features,
		}

		geojson_str = json.dumps(geojson_dict, ensure_ascii=False).encode('utf8')

		zip.writestr(prefix + _sanitize_filename(question.name) + '.geojson', geojson_str)

	#обработка обычных вопросов

	sessions = survey.sessions()

	properties_list = []
	for session in sessions:
		# Skip excluded sessions
		if session.id in excluded_session_ids:
			continue

		properties = {}
		answers = session.answers()
		for answer in answers:
			if not answer.question:
				continue

			cell = _answer_cell(answer.question, [answer])
			# Geometry questions are exported as their own GeoJSON layers and
			# display-only questions collect nothing, so neither gets a column.
			if cell is EXPORT_NO_COLUMN:
				continue

			# A ranking answer is several columns, not one cell.
			if isinstance(cell, dict):
				properties.update(cell)
			elif (answer.question.input_type in _FILE_TYPES
					and properties.get(answer.question.name)):
				# Several files on one question: one cell listing every path.
				properties[answer.question.name] += '; ' + cell
			else:
				properties[answer.question.name] = cell

		properties["session"] = str(session)
		properties["session_id"] = session.id
		properties["datetime"] = session.start_datetime
		properties["language"] = session.language or ''
		properties["validation_status"] = session.validation_status or ''
		properties_list.append(properties)

	zip.writestr(prefix + _sanitize_filename(survey.name) + '.csv', pd.DataFrame(properties_list).to_csv())

	# Respondent files ride along under files/<session_id>/, read through the
	# storage API so the same code serves filesystem and S3. Only attached
	# uploads of non-excluded sessions — orphans and trashed sessions stay out.
	file_answers = (
		Answer.objects
		.filter(
			survey_session__survey=survey,
			question__input_type__in=_FILE_TYPES,
			upload__isnull=False,
		)
		.exclude(survey_session_id__in=excluded_session_ids)
		.select_related('question', 'upload')
	)
	for answer in file_answers:
		try:
			with answer.upload.file.open('rb') as stored:
				zip.writestr(prefix + _upload_archive_path(answer.question, answer), stored.read())
		except Exception:
			logger.warning(
				"Export: upload %s missing from storage; row keeps the path, file absent from ZIP.",
				answer.upload_id,
			)


@survey_permission_required('viewer')
def export_survey(request, survey_uuid):
	"""Export survey to ZIP archive with specified mode."""
	mode = request.GET.get('mode', 'structure')

	if mode not in EXPORT_MODES:
		messages.error(request, f"Invalid export mode '{mode}'")
		return redirect('editor')

	survey = request.survey

	try:
		in_memory = BytesIO()
		warnings = export_survey_to_zip(survey, in_memory, mode)

		# Show warnings as messages
		for warning in warnings:
			messages.warning(request, warning)

		response = HttpResponse(content_type="application/zip")
		response["Content-Disposition"] = f"attachment; filename=survey_{_sanitize_filename(survey.name)}_{mode}.zip"

		in_memory.seek(0)
		response.write(in_memory.read())

		return response

	except ExportError as e:
		messages.error(request, str(e))
		return redirect('editor')


@org_permission_required('editor')
def import_survey(request):
	"""Import survey from uploaded ZIP archive."""
	if request.method != 'POST':
		return redirect('editor')

	if 'file' not in request.FILES:
		messages.error(request, "No file uploaded")
		return redirect('editor')

	uploaded_file = request.FILES['file']

	try:
		survey, warnings = import_survey_from_zip(
			uploaded_file,
			organization=request.active_org,
			created_by=request.user,
		)

		# Show warnings
		for warning in warnings:
			messages.warning(request, warning)

		if survey:
			# Create SurveyCollaborator owner entry for imported survey
			SurveyCollaborator.objects.get_or_create(
				user=request.user,
				survey=survey,
				defaults={'role': 'owner'},
			)
			messages.success(request, f"Survey '{survey.name}' imported successfully")
		else:
			messages.success(request, "Data imported successfully")

	except SerializationImportError as e:
		messages.error(request, str(e))

	return redirect('editor')


STORIES_CRUMB = Crumb("Stories", "/stories/")


def stories_index(request):
	"""Public stories hub at /stories/ — card grid of published stories, newest first."""
	stories = list(Story.objects.filter(is_published=True).order_by('-published_date'))
	breadcrumbs = (HOME, STORIES_CRUMB)
	context = {
		'stories': stories,
		'breadcrumb_jsonld': build_breadcrumb_jsonld(breadcrumbs),
		'collection_jsonld': build_story_collection_jsonld(request, stories) if stories else "",
	}
	return render(request, 'stories_index.html', context)


def story_detail(request, slug):
	from django.utils.html import strip_tags
	try:
		story = Story.objects.select_related('survey').get(slug=slug, is_published=True)
	except Story.DoesNotExist:
		raise Http404
	excerpt = " ".join(strip_tags(story.body or "").split())
	meta_description = (excerpt[:155].rstrip() + "…") if len(excerpt) > 155 else (excerpt or story.title)
	breadcrumbs = (HOME, STORIES_CRUMB, Crumb(story.title, f"/stories/{story.slug}/"))
	context = {
		'story': story,
		'canonical': f"https://mapsurvey.org/stories/{story.slug}/",
		'meta_description': meta_description,
		'breadcrumb_jsonld': build_breadcrumb_jsonld(breadcrumbs),
	}
	return render(request, 'story_detail.html', context)


def public_results(request, slug):
	"""Public, read-only results page served at /r/<slug>/.

	404 unless the page exists and is published. Renders live aggregates
	or a frozen snapshot. Unlisted pages are reachable here but emit
	noindex and are excluded from listings/sitemap.
	"""
	from .models import PublicResultsPage
	from .public_results import build_page_context

	page = get_object_or_404(
		PublicResultsPage.objects.select_related('survey'),
		slug=slug, is_published=True,
	)
	lang = request.GET.get('lang') or 'en'
	return render(request, 'public_results.html', build_page_context(page, lang=lang))


@survey_permission_required('owner')
def delete_survey(request, survey_uuid):
	"""Move a survey to trash (soft-delete); recoverable for 30 days."""
	if request.method != 'POST':
		messages.error(request, "Invalid request method")
		return redirect('editor')

	survey = request.survey
	trash_survey(survey)
	audit(request, 'survey_trash', survey)
	messages.success(request, f"Survey '{survey.name}' moved to Trash. You can restore it within {SurveyHeader.TRASH_RETENTION_DAYS} days.")

	return redirect('editor')


@survey_permission_required('owner', allow_trashed=True)
def restore_survey_view(request, survey_uuid):
	"""Restore a survey from trash to its exact pre-trash state."""
	if request.method != 'POST':
		messages.error(request, "Invalid request method")
		return redirect('editor')

	survey = request.survey
	if not survey.is_trashed:
		messages.error(request, "Survey is not in Trash")
		return redirect('editor')

	restore_survey(survey)
	audit(request, 'survey_restore', survey)
	messages.success(request, f"Survey '{survey.name}' restored")

	return redirect('editor')


@csrf_exempt
@require_POST
def internal_purge_trash(request):
	"""Run auto-purge of expired trashed surveys; driven by an external cron.

	Authenticated with the PURGE_TASK_TOKEN shared secret (empty token
	disables the endpoint). See survey-deletion-safety spec, survey-trash.
	"""
	token = conf_settings.PURGE_TASK_TOKEN
	provided = request.headers.get('Authorization', '')
	if provided.startswith('Bearer '):
		provided = provided[len('Bearer '):]
	if not token or not hmac.compare_digest(provided, token):
		return HttpResponseForbidden()

	purged = purge_expired_surveys()
	return JsonResponse({'purged': purged})


@survey_permission_required('owner', allow_trashed=True)
def purge_survey_view(request, survey_uuid):
	"""Permanently delete a trashed survey, its data and media files."""
	if request.method != 'POST':
		messages.error(request, "Invalid request method")
		return redirect('editor')

	survey = request.survey
	if not survey.is_trashed:
		messages.error(request, "Only surveys in Trash can be deleted forever")
		return redirect('editor')

	name = survey.name
	audit(request, 'survey_purge', survey)
	purge_survey(survey)
	messages.success(request, f"Survey '{name}' deleted forever")

	return redirect('editor')


def survey_password_gate(request, survey_slug):
	survey = resolve_survey(survey_slug)
	# The only respondent view that does not go through check_survey_access --
	# it *is* the denial. Flag it directly so the gate for an unpublished survey
	# is not indexable either.
	mark_indexing(request, survey)
	error = None

	if request.method == 'POST':
		password = request.POST.get('password', '')
		if survey.check_password(password):
			request.session[f'survey_password_{survey.id}'] = True
			# Also grant test access if in testing state
			if survey.status == 'testing':
				request.session[f'test_access_{survey.id}'] = True
			return redirect('survey', survey_slug=str(survey.uuid))
		else:
			error = 'Incorrect password'

	return render(request, 'survey_password.html', {
		'survey': survey,
		'error': error,
	})


def survey_layer_geojson(request, survey_slug, layer_id):
	"""Serve a reference layer's GeoJSON under the survey's own access rules.

	Never a raw storage URL: the S3 media bucket is public-read, and a draft
	survey's layer must be as invisible as the draft itself. Any access denial
	collapses to 404 — a fetch() consumer can't follow the password/closed
	redirects the page views return, and a bare 404 keeps drafts
	indistinguishable from nonexistent surveys.
	"""
	from django.conf import settings as django_settings
	if not django_settings.MAP_REFERENCE_LAYERS:
		raise Http404
	survey = resolve_survey(survey_slug)
	if check_survey_access(request, survey) is not None:
		raise Http404
	layer = get_object_or_404(SurveyMapLayer, pk=layer_id, survey=survey)

	etag = '"layer-%s-%s"' % (layer.pk, layer.updated_at.strftime('%Y%m%d%H%M%S%f'))
	if request.headers.get('If-None-Match') == etag:
		response = HttpResponse(status=304)
	else:
		response = HttpResponse(layer.geojson, content_type='application/geo+json')
	response['ETag'] = etag
	response['Cache-Control'] = 'private, max-age=300'
	return response


def survey_thanks(request, survey_slug):
	survey = resolve_survey(survey_slug)

	# Allow access if user just completed the survey (has active session)
	has_active_session = 'survey_session_id' in request.session
	if not has_active_session:
		access_response = check_survey_access(request, survey)
		if access_response:
			return access_response

	# Emit survey_complete event before clearing session
	session_id = request.session.get('survey_session_id')
	if session_id:
		try:
			_sess = SurveySession.objects.get(pk=session_id)
			emit_event(_sess, 'survey_complete')
		except SurveySession.DoesNotExist:
			pass

	lang = request.session.pop('survey_language', None)
	request.session.pop('survey_session_id', None)

	thanks_html = resolve_thanks_html(survey.thanks_html, lang)

	return render(request, 'survey_thanks.html', {
		'survey': survey,
		'thanks_html': thanks_html,
		'lang': lang or 'en',
	})


# Creator-authored WYSIWYG HTML (thanks page, Formatted Text block) is sanitized in
# survey.html_sanitize; the thanks-era names are kept here as aliases so existing
# call sites and tests read unchanged.
from .html_sanitize import (  # noqa: E402
	sanitize_creator_html,
	CREATOR_HTML_ALLOWED_TAGS as THANKS_HTML_ALLOWED_TAGS,
	CREATOR_HTML_ALLOWED_ATTRS as THANKS_HTML_ALLOWED_ATTRS,
	CREATOR_VIDEO_HOSTS as THANKS_VIDEO_HOSTS,
)

sanitize_thanks_html = sanitize_creator_html


def resolve_thanks_html(thanks_html, lang):
	"""Resolve thanks_html content by language.

	Accepts a dict keyed by language code or a plain string.
	Fallback chain: requested lang → "en" → first available → None.
	"""
	if not thanks_html:
		return None
	if isinstance(thanks_html, str):
		return thanks_html
	if isinstance(thanks_html, dict):
		if lang and lang in thanks_html:
			return thanks_html[lang]
		if 'en' in thanks_html:
			return thanks_html['en']
		if thanks_html:
			return next(iter(thanks_html.values()))
	return None


@lang_override('en')
def trust_page(request):
	return render(request, 'trust.html')


def for_educators(request):
	"""Public "Mapsurvey for classrooms" landing page (SEO + coursework acquisition, H1).

	First-touch source capture so a search/referral -> educators -> register flow is
	attributed (Phase-1). The page's CTAs also carry utm_source=edu.
	"""
	return render_seo_landing(request, 'for_educators')


def maptionnaire_alternative(request):
	"""Public "free, open-source Maptionnaire alternative" comparison page.

	Targets the validated "Maptionnaire alternative" search intent (how Jaakko
	found us). First-touch source capture; CTAs carry utm_source=comparison.
	"""
	return render_seo_landing(request, 'maptionnaire_alternative')


def for_planners(request):
	"""Public "Mapsurvey for urban planners & community engagement" landing page.

	The core participatory-planning market (Maptionnaire's turf). First-touch
	source capture; CTAs carry utm_source=planners.
	"""
	return render_seo_landing(request, 'for_planners')


def for_researchers(request):
	"""Public "Mapsurvey for participatory & spatial research" landing page.

	PPGIS / participatory research + citizen science. First-touch source capture;
	CTAs carry utm_source=researchers.
	"""
	return render_seo_landing(request, 'for_researchers')


def for_government(request):
	"""Public landing page: the open-source community engagement platform for
	local government. Audience page (councils / public agencies) that also owns
	the "community engagement platform" positioning. utm_source=government."""
	return render_seo_landing(request, 'for_government')


def community_engagement_platform(request):
	"""Public product landing page owning the "community engagement platform" head term.

	Product/category framing (cross-audience: councils, NGOs, consultancies, universities,
	transport agencies) — distinct from the audience page /for-government/, which scopes the
	same term to local government. First-touch source capture; CTAs carry
	utm_source=engagement_platform."""
	return render_seo_landing(request, 'community_engagement_platform')


def public_consultation_software(request):
	"""Public product landing page owning the "public consultation software" term.

	Consultation-workflow framing (statutory consultation, planning applications,
	infrastructure) — audience wider than government. First-touch source capture; CTAs carry
	utm_source=consultation_software."""
	return render_seo_landing(request, 'public_consultation_software')


def civic_engagement(request):
	"""Public category page owning the "civic engagement" cluster (civic engagement /
	civic involvement / civic participation — the largest measured keyword gap).

	Middle-funnel semantic anchor: explains map-based civic engagement and funnels down
	to the product pages. CTAs carry utm_source=civic_engagement."""
	return render_seo_landing(request, 'civic_engagement')


def participatory_budgeting(request):
	"""Public use-case page for map-based participatory budgeting.

	Honest scope: location input for PB programmes (where residents want investment),
	explicitly not a budget-allocation module. CTAs carry utm_source=participatory_budgeting."""
	return render_seo_landing(request, 'participatory_budgeting')


def for_consultants(request):
	"""Public audience page for engagement & planning consultancies.

	Leads with per-project economics (no per-project fees), GeoJSON deliverables, and
	open-source self-hosting. CTAs carry utm_source=consultants."""
	return render_seo_landing(request, 'for_consultants')


def social_pinpoint_alternative(request):
	"""Public "open-source Social Pinpoint alternative" comparison page.

	Claims restricted to the verified dossier (docs/marketing/competitors/openpoint.md).
	CTAs carry utm_source=comparison / utm_medium=social_pinpoint_alt."""
	return render_seo_landing(request, 'social_pinpoint_alternative')


def metroquest_alternative(request):
	"""Public "MetroQuest alternative" page for customers of the sunset MetroQuest product.

	Migration framing: metroquest.com now redirects into Open Point. CTAs carry
	utm_source=comparison / utm_medium=metroquest_alt."""
	return render_seo_landing(request, 'metroquest_alternative')


def services(request):
	"""Public "Expert help" service page: optional paid help with survey design
	and getting real responses, on top of the free self-serve platform. Targets
	the verified gap where teams build+publish but collect ~0 responses.
	utm_source=services."""
	capture_signup_source(request)
	return render(request, 'services.html')


def robots_txt(request):
	lines = [
		"User-agent: *",
		"Allow: /surveys/",
		"Allow: /stories/",
		"Allow: /services/",
		"Allow: /r/",
	]
	# SEO landing pages — derived from the single-source registry
	# (survey/seo_landings.py) so a new landing can't silently miss the allow-list.
	for landing in SEO_LANDINGS:
		lines.append(f"Allow: {landing.path}")
	lines += [
		"Disallow: /admin/",
		"Disallow: /editor/",
		"Disallow: /accounts/",
		"",
		f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
	]
	return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
	base = f"{request.scheme}://{request.get_host()}"
	# Only surveys that actually open for an anonymous visitor. Before this,
	# 108 of the 140 entries here were 404s, duplicates or dead ends.
	surveys = publicly_visible_surveys()
	urls = [f"  <url><loc>{base}/</loc></url>"]
	urls.append(f"  <url><loc>{base}/services/</loc></url>")
	# SEO landing pages with crawl hints — from the single-source registry.
	for landing in SEO_LANDINGS:
		urls.append(
			f"  <url><loc>{base}{landing.path}</loc>"
			f"<lastmod>{landing.lastmod}</lastmod>"
			f"<changefreq>{landing.changefreq}</changefreq>"
			f"<priority>{landing.priority}</priority></url>"
		)
	urls.append(f"  <url><loc>{base}/trust/</loc></url>")
	# `/surveys/` itself is not listed: it now redirects to `/`, and a sitemap
	# should not advertise a redirect. Individual `/surveys/<uuid>/` entries below
	# are still listed.
	# Stories hub + published stories
	urls.append(f"  <url><loc>{base}/stories/</loc></url>")
	for story in Story.objects.filter(is_published=True).order_by('-published_date'):
		lastmod = f"<lastmod>{story.published_date.date().isoformat()}</lastmod>" if story.published_date else ""
		urls.append(f"  <url><loc>{base}/stories/{story.slug}/</loc>{lastmod}</url>")
	for survey in surveys:
		urls.append(f"  <url><loc>{base}/surveys/{survey.uuid}/</loc></url>")
	# Public (indexable) results pages; unlisted pages are excluded.
	from .models import PublicResultsPage
	for page in PublicResultsPage.objects.filter(is_published=True, visibility='public'):
		urls.append(f"  <url><loc>{base}/r/{page.slug}/</loc></url>")
	xml = (
		'<?xml version="1.0" encoding="UTF-8"?>\n'
		'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
		+ "\n".join(urls)
		+ "\n</urlset>"
	)
	return HttpResponse(xml, content_type="application/xml")

@require_POST
def survey_upload(request, survey_slug):
	"""Async respondent file upload — the only route that accepts file bytes.

	Forms and geo-popup properties carry the returned token, never the file;
	the section POST resolves tokens to Upload rows and attaches them. Bytes
	must arrive before submit because a popup answer exists client-side long
	before the section is posted.

	Anonymous by nature, so layered like registration: a real survey_session
	for THIS survey, the named question must be a file type in it, per-type
	allow-lists with magic-byte checks, a size cap, per-session count/byte
	caps, and an IP rate limit (fail-open on Redis outage, the established
	posture).
	"""
	from django.conf import settings as conf_settings
	from .models import Upload
	from .uploads import UploadRejected, check_session_caps, validate_upload

	if not getattr(conf_settings, 'FILE_UPLOAD_QUESTIONS', False):
		raise Http404

	survey = resolve_survey(survey_slug)
	access_response = check_survey_access(request, survey)
	if access_response is not None:
		raise Http404

	session_id = request.session.get('survey_session_id')
	survey_session = SurveySession.objects.filter(
		id=session_id, survey=survey, is_deleted=False,
	).first() if session_id else None
	if survey_session is None and request.user.is_authenticated:
		# The editor's Live Preview frames the respondent page without a
		# respondent session — and on mobile the preview IS how creators test.
		# A collaborator gets one lazily-created session per survey, tagged so
		# it is visible (and trashable) in Responses like any other row.
		role = get_effective_survey_role(request.user, survey)
		if SURVEY_ROLE_RANK.get(role, -1) >= SURVEY_ROLE_RANK['viewer']:
			survey_session = (
				SurveySession.objects
				.filter(survey=survey, is_deleted=False, tags__contains=['editor-preview'])
				.first()
			) or SurveySession.objects.create(survey=survey, tags=['editor-preview'])
	if survey_session is None:
		# A real respondent lands here when cookies are blocked or the page
		# outlived its session — "reload" is the action that actually helps.
		return JsonResponse({'error': 'no_session',
		                     'message': _('Please reload the survey page and try again.')}, status=403)

	question = Question.objects.filter(
		survey_section__survey_header=survey,
		code=request.POST.get('question', ''),
		input_type__in=FILE_INPUT_TYPES,
	).first()
	if question is None:
		return JsonResponse({'error': 'unknown_question',
		                     'message': _('This question does not accept files.')}, status=400)

	if is_ratelimited(request, group='survey_upload', key='ip',
	                  rate='60/h', method=['POST'], increment=True):
		return JsonResponse({'error': 'rate_limited',
		                     'message': _('Too many uploads, try again later.')}, status=429)

	uploaded = request.FILES.get('file')
	if uploaded is None:
		return JsonResponse({'error': 'no_file', 'message': _('No file received.')}, status=400)

	try:
		check_session_caps(survey_session)
		content_type = validate_upload(question, uploaded)
	except UploadRejected as rejection:
		return JsonResponse({'error': rejection.code, 'message': str(rejection.message)}, status=400)

	# The stored name is sanitized by Django's storage; the original stays on
	# the row for humans (responses table, ZIP) and is always rendered as text.
	upload = Upload.objects.create(
		session=survey_session,
		question=question,
		file=uploaded,
		original_name=uploaded.name[:255],
		content_type=content_type,
		size=uploaded.size,
	)
	return JsonResponse({'token': str(upload.token),
	                     'name': upload.original_name,
	                     'size': upload.size})
