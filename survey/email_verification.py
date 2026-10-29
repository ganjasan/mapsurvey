"""Email confirmation and the sign-in grace period (change login-grace-period, #487).

A new account signs in at once and has SIGN_IN_GRACE_HOURS to confirm its
address. Past that, a correct password is refused with the real reason and a
fresh link goes out; the link (which signs in on confirmation) is the only way
back in. Nothing goes live from an unconfirmed address: publishing and
workspace invitations wait for it.

This module is the ONE rule. Sign-in (`survey.backends`, `survey.auth_forms`),
the session check (`survey.middleware.GracePeriodMiddleware`), the services,
the API/OAuth gates and the funnel ask it; none of them computes a deadline.

`User.is_active` means only "not banned" (`content_screening.confirm_phishing`).
An account with no `EmailVerification` row is confirmed — superusers, admin-made
staff, fixtures; registration always writes a row.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# The per-address cap every activation mail shares (resend form, banner button,
# refused sign-in, ended session), RESEND_ACTIVATION_RATE_LIMIT_DAY a day. Any
# HTTP method counts: an ended session is noticed on a GET.
RESEND_GROUP = 'activation_mail_day'


def _record(user):
    from .models import EmailVerification
    try:
        return user.email_verification
    except EmailVerification.DoesNotExist:
        return None


def is_verified(user):
    record = _record(user)
    return record is None or record.verified_at is not None


def confirmed_q(prefix=''):
    """Queryset filter for "address confirmed" over users (`prefix` = the path
    to the user, e.g. 'user__'). No row counts as confirmed."""
    from django.db.models import Q
    return (Q(**{f'{prefix}email_verification__isnull': True})
            | Q(**{f'{prefix}email_verification__verified_at__isnull': False}))


def grace_deadline(user):
    return user.date_joined + timedelta(hours=settings.SIGN_IN_GRACE_HOURS)


def in_grace(user, now=None):
    return (now or timezone.now()) < grace_deadline(user)


def can_sign_in(user, now=None):
    """Not banned, and confirmed or still inside the grace period."""
    if not getattr(user, 'is_active', False):
        return False
    return is_verified(user) or in_grace(user, now)


def awaits_confirmation(user, now=None):
    """Active, unconfirmed and past the deadline: the one case that is told why."""
    return bool(getattr(user, 'is_active', False)) and not is_verified(user) and not in_grace(user, now)


def mark_verified(user):
    """Confirm the address. Returns False when it already was confirmed."""
    from .models import EmailVerification
    now = timezone.now()
    record, created = EmailVerification.objects.get_or_create(user=user, defaults={'verified_at': now})
    if created:
        return True
    if record.verified_at is not None:
        return False
    record.verified_at = now
    record.save(update_fields=['verified_at'])
    return True


def start_unverified(user):
    """The registration row: unconfirmed, a mail about to go out."""
    from .models import EmailVerification
    EmailVerification.objects.update_or_create(
        user=user, defaults={'verified_at': None, 'last_sent_at': timezone.now()},
    )


def mask_email(email):
    """`a•••@example.org` — enough for the owner to recognise, little for anyone else."""
    local, sep, domain = (email or '').partition('@')
    if not sep:
        return '•••'
    return f'{local[:1]}•••@{domain}'


def _limited(request, email):
    from django_ratelimit import ALL
    from django_ratelimit.core import is_ratelimited
    try:
        return is_ratelimited(
            request=request, group=RESEND_GROUP, fn=None,
            key=lambda _group, _request: email.strip().lower(),
            rate=f'{settings.RESEND_ACTIVATION_RATE_LIMIT_DAY}/d',
            method=ALL,
            increment=True,
        )
    except Exception:  # noqa: BLE001 — a blind limiter must not stop the mail (fail-open)
        logger.warning('resend rate limit unavailable; sending', exc_info=True)
        return False


def send_link(user, request, *, source):
    """Send an activation mail to an unconfirmed, non-banned account.

    Returns True when a mail went out, False when the per-address daily cap
    was already spent (or the account needs no mail). `source` is for the log
    line only: register | resend_form | banner | sign_in | session_end.
    """
    if not user.is_active or is_verified(user) or not user.email:
        return False
    if _limited(request, user.email):
        from .abuse import log_abuse_event
        log_abuse_event('ratelimit', request, f'resend_day:{source}')
        return False
    from .models import EmailVerification
    from .views import AsyncEmailRegistrationView

    view = AsyncEmailRegistrationView()
    view.request = request
    view.send_activation_email(user)
    EmailVerification.objects.filter(user=user).update(last_sent_at=timezone.now())
    logger.info('activation link sent user=%s source=%s', user.pk, source)
    return True


# --- the migration rule ------------------------------------------------------

def classify(is_active, last_login, banned):
    """What an existing account becomes. Pure; shared by migration 0111 and
    `sync_email_verification`.

    Returns (is_active, verified): active accounts are confirmed; an inactive
    account that never signed in registered and never activated, so it becomes
    active and unconfirmed (grace long over); an inactive account that signed
    in, or whose survey was confirmed as phishing, is banned and stays so.
    """
    if is_active:
        return True, True
    if last_login is None and not banned:
        return True, False
    return False, True


def sync_accounts(User, EmailVerification, ContentReview):
    """Give every account without a row one, by `classify`. Idempotent.

    Takes model classes so the data migration can pass historical models.
    Returns (confirmed, unconfirmed) counts of rows created.
    """
    banned_ids = set(
        ContentReview.objects.filter(status='confirmed', survey__created_by__isnull=False)
        .values_list('survey__created_by_id', flat=True)
    )
    confirmed = unconfirmed = 0
    missing = User.objects.filter(email_verification__isnull=True)
    for user in missing.iterator():
        is_active, verified = classify(user.is_active, user.last_login, user.pk in banned_ids)
        if is_active != user.is_active:
            user.is_active = is_active
            user.save(update_fields=['is_active'])
        EmailVerification.objects.create(
            user=user,
            verified_at=(user.last_login or user.date_joined) if verified else None,
        )
        if verified:
            confirmed += 1
        else:
            unconfirmed += 1
    return confirmed, unconfirmed
