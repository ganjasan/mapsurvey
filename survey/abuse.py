"""Abuse-prevention helpers for the registration endpoint.

Three defenses are wired into AbuseProtectedRegistrationView (in survey/views.py):
  1. Cloudflare Turnstile (verify_turnstile)
  2. Per-IP rate limit (django-ratelimit invoked from view dispatch)
  3. Honeypot field (the `website` field added by RegistrationAbuseForm)

Every triggered defense writes one AbuseEvent row via log_abuse_event() and
emits one log line on the abuse logger. The audit table is queried by the
future Phase 3 anomaly dashboard.

The honeypot field name is hardcoded as "website" — it travels through three
layers (form, view, template) and a configurable name buys nothing real
(the upstream RegistrationForm has no `website` field, no collision risk).
The form lives here rather than in survey/forms.py because it is tightly
coupled to the rest of this module's logic.

See openspec/changes/add-registration-abuse-defenses/ for the full design.
"""

import json
import logging
from urllib import request as urllib_request
from urllib.parse import urlencode
from urllib.error import URLError

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django_registration.forms import RegistrationForm
from django_ratelimit.core import get_usage, is_ratelimited


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT_SECONDS = 5
HONEYPOT_FIELD_NAME = "website"


def client_ip(request):
    """Return the trusted client IP for `request`.

    Reads request.cf_ip (set by CloudflareIPMiddleware). Falls back to
    REMOTE_ADDR if for some reason the middleware did not run (e.g. a
    test that bypasses middleware). Used as the remoteip parameter on
    Turnstile siteverify.
    """
    return (
        getattr(request, "cf_ip", None)
        or request.META.get("REMOTE_ADDR", "")
    )


def ratelimit_key(group, request):
    """Adapter for django-ratelimit's `key` callable signature.

    django-ratelimit invokes the key callable as `keyfn(group, request)`.
    We just want the IP — delegate to client_ip(). Kept as a separate
    function so client_ip() stays usable everywhere else with the natural
    single-argument signature.
    """
    return client_ip(request)


def ratelimit_email_key(group, request):
    """Rate-limit key over the submitted email, for the resend endpoint.

    The per-IP limit alone does not protect a *victim*: an attacker rotating
    IPs could still hammer one inbox. Keying a second limit on the normalized
    target address caps how many activation emails any single address can
    receive per day, regardless of origin.

    Falls back to the IP when no email was submitted, so a malformed POST
    still consumes a bucket instead of bypassing the limit entirely.
    """
    email = (request.POST.get("email") or "").strip().lower()
    return email or client_ip(request)


def registration_limits(kind):
    """Return the (group, rate, retry_after, detail) tuples for one counter set.

    `kind` is "valid" or "invalid". The two sets use different django-ratelimit
    group names, so they are independent buckets in Redis sharing one key
    function (the client IP).
    """
    if kind == "invalid":
        return (
            ("registration_invalid_hour",
             f"{settings.REGISTRATION_INVALID_LIMIT_HOUR}/h", 3600, "invalid_hour"),
            ("registration_invalid_day",
             f"{settings.REGISTRATION_INVALID_LIMIT_DAY}/d", 86400, "invalid_day"),
        )
    return (
        ("registration_hour",
         f"{settings.REGISTRATION_RATE_LIMIT_HOUR}/h", 3600, "hour"),
        ("registration_day",
         f"{settings.REGISTRATION_RATE_LIMIT_DAY}/d", 86400, "day"),
    )


def check_registration_limit(request, kind):
    """Return (retry_after, detail) if `kind`'s limit is already exceeded.

    Read-only: never advances a counter. Called before form processing so an
    already-limited IP is refused without the cost of validating the form or
    the network round-trip to Cloudflare.

    Uses get_usage() rather than is_ratelimited() because the two ask different
    questions. is_ratelimited() reports `count > limit`, which is correct when
    the same call also increments — the request being counted is the one that
    tips it over. Here the increment happens later, so the question is whether
    the budget is *already* spent: `count >= limit`. Using is_ratelimited() here
    would let through exactly one attempt more than configured.

    Fail-open: any cache-backend exception (Redis outage) is swallowed and
    treated as "not limited", so a Redis outage cannot stop legitimate
    signups. Honeypot and Turnstile still apply while the limiter is blind.
    """
    for group, rate, retry_after, detail in registration_limits(kind):
        try:
            usage = get_usage(
                request=request,
                group=group,
                fn=None,
                key="survey.abuse.ratelimit_key",
                rate=rate,
                method="POST",
                increment=False,
            )
            limited = usage is not None and usage["count"] >= usage["limit"]
        except Exception:
            limited = False
        if limited:
            return retry_after, detail
    return None


def increment_registration_limit(request, kind):
    """Advance `kind`'s counters by one. Called once validity is known.

    Split from check_registration_limit() deliberately: checking early is
    correct (it is cheap and short-circuits), but counting early is what
    turned three password typos into an hour-long lockout. Validity is the
    signal that separates a confused human from a bot, and it is not
    available until the form has been validated.
    """
    for group, rate, _retry_after, _detail in registration_limits(kind):
        try:
            is_ratelimited(
                request=request,
                group=group,
                fn=None,
                key="survey.abuse.ratelimit_key",
                rate=rate,
                method="POST",
                increment=True,
            )
        except Exception:
            pass


def verify_turnstile(token, remote_ip=""):
    """Return True if `token` is accepted by Cloudflare's siteverify endpoint.

    Returns True without making any HTTP call when settings.TURNSTILE_SECRET_KEY
    is empty — this keeps `manage.py runserver` workable for developers who
    have not configured Turnstile keys.

    Returns False on missing token, siteverify rejection, network error, or
    timeout. Fail-closed: a Cloudflare outage blocks new registrations rather
    than letting bots through.
    """
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
    if not secret:
        return True
    if not token:
        return False
    payload = urlencode({
        "secret": secret,
        "response": token,
        "remoteip": remote_ip,
    }).encode("utf-8")
    try:
        with urllib_request.urlopen(
            TURNSTILE_VERIFY_URL,
            data=payload,
            timeout=TURNSTILE_TIMEOUT_SECONDS,
        ) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, ValueError):
        return False
    return bool(result.get("success", False))


def log_abuse_event(defense, request, detail=""):
    """Persist one AbuseEvent row and emit one log line on the abuse logger.

    Single write path for all defenses — keeps schema consistency and makes
    the future anomaly dashboard a one-line query. The model is imported
    lazily so this module stays importable from settings/middleware code.

    DB failures during AbuseEvent.create() are swallowed: the defense response
    (302/429/form re-render) must reach the client even if the audit log
    write fails, otherwise a DB outage would fingerprint our defenses by
    surfacing 500s where bots otherwise see fake-success.
    """
    from .models import AbuseEvent

    ip = client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:1024]
    logger = logging.getLogger(f"abuse.{defense}")
    try:
        AbuseEvent.objects.create(
            defense=defense,
            ip=ip or None,
            user_agent=user_agent,
            detail=detail,
        )
    except Exception:
        logger.exception("Failed to persist AbuseEvent for defense=%s", defense)
    logger.warning(
        "%s triggered ip=%s detail=%s ua=%r",
        defense, ip, detail, user_agent[:120],
    )


class RegistrationAbuseForm(RegistrationForm):
    """Adds a hidden honeypot `website` field to the upstream RegistrationForm.

    The form's only job is to render the field in the HTML — the actual
    honeypot check lives in the view, which inspects request.POST directly
    BEFORE form validation. That way a bot submitting both a filled
    honeypot AND invalid form data (e.g. password mismatch) still gets the
    fake-success redirect rather than a form-error 200 that would
    fingerprint the defense.

    Turnstile validation is also handled in the view — it needs `request`
    to read `cf-turnstile-response` (with dash, not Python-friendly).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[HONEYPOT_FIELD_NAME] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }),
            label="",
        )
        # Django's stock username help text is "Required. 150 characters or
        # fewer. Letters, digits and @/./+/-/_ only." — it leads with a ceiling
        # no human input approaches and buries the part that can actually
        # reject a submission. Help text should name the wall someone can walk
        # into, not the one they cannot reach.
        for name in ("username", get_user_model().USERNAME_FIELD):
            if name in self.fields:
                self.fields[name].help_text = _(
                    "Letters, digits and @ . + - _ only. No spaces."
                )
        # The live checklist rendered under the password field carries the
        # rules now; the stock paragraph duplicated them as unstyled prose.
        for name in ("password1", "password2"):
            if name in self.fields:
                self.fields[name].help_text = ""


class ResendActivationForm(forms.Form):
    """Single email field plus the same hidden honeypot as registration.

    As with RegistrationAbuseForm, the honeypot check itself lives in the
    view (read from request.POST before validation) so a bot that fills the
    honeypot AND submits a malformed email still gets the neutral response
    rather than a form-error page that would fingerprint the defense.
    """

    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[HONEYPOT_FIELD_NAME] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }),
            label="",
        )
