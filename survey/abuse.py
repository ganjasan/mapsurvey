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
from django_registration.forms import RegistrationForm


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
