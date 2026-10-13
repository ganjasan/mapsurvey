""""Request a demo" — the two-step lead form at `/demo/` (change request-demo-form).

Step one asks for an email and nothing else; step two asks for the details that
help us prepare. Each submitted step stores, notifies `CONTACT_EMAIL` and emits
one `demo_requested` event, so a visitor who stops after step one is still a
lead we can answer.

Deliberately no auto-reply to the submitted address: a form that mails whatever
address it is given is an open relay. The reply is written by hand.
"""
import logging

from django import forms
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .analytics_ids import anonymous_distinct_id
from .models import DemoRequest

logger = logging.getLogger(__name__)

DEMO_REQUESTED = 'demo_requested'

# Marketing surfaces that link to /demo/?src=<surface>. Anything else -- a typo,
# a hand-edited URL, a crawler -- is stored as 'direct' so the column stays a
# closed set that a breakdown can trust.
SOURCES = frozenset({'hero', 'how_to_start', 'services', 'educators', 'footer'})
DEFAULT_SOURCE = 'direct'

# Step two stops accepting edits after this long; the row is a lead by then.
DETAILS_WINDOW_DAYS = 7


def normalise_source(value):
    value = (value or '').strip()
    return value if value in SOURCES else DEFAULT_SOURCE


class DemoEmailForm(forms.Form):
    email = forms.EmailField(
        label=_("Work email"),
        max_length=254,
        error_messages={
            'required': _("We need an email to write back to."),
            'invalid': _("That does not look like an email address."),
        },
    )


class DemoDetailsForm(forms.Form):
    name = forms.CharField(label=_("Your name"), max_length=200, required=False)
    organisation = forms.CharField(label=_("Organisation"), max_length=200, required=False)
    project = forms.CharField(
        label=_("What do you want to map?"), required=False, max_length=4000,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    timeline = forms.ChoiceField(
        label=_("When?"), required=False,
        choices=(('', '—'),) + DemoRequest.TIMELINE_CHOICES,
    )


def notify(row, stage):
    """Mail `CONTACT_EMAIL` about one submitted step, once the row is committed.

    Enqueued on commit so the worker never races the transaction. If the broker
    is unreachable the mail goes inline; if that fails too, the row is still
    stored and listed in the admin -- a lost email must never lose the lead.
    """
    def send():
        from .tasks import notify_demo_request
        try:
            notify_demo_request.delay(row.pk, stage)
        except Exception:  # noqa: BLE001 — broker down: send inline
            logger.exception('could not enqueue demo notification %s/%s; sending inline', row.pk, stage)
            try:
                send_notification(row, stage, fail_silently=True)
            except Exception:  # noqa: BLE001
                logger.exception('inline demo notification %s/%s failed', row.pk, stage)

    transaction.on_commit(send)


def send_notification(row, stage, fail_silently=False):
    from django.conf import settings
    from django.urls import reverse

    from .mail import absolute_url, send_templated_mail

    to = getattr(settings, 'CONTACT_EMAIL', '')
    if not to:
        logger.warning('demo request %s: CONTACT_EMAIL is empty, nothing sent', row.pk)
        return 0
    if stage == 'details':
        subject = f"Demo request details: {row.email}"
        if row.organisation:
            subject += f" — {row.organisation}"
    else:
        subject = f"Demo request: {row.email}"
    context = {
        'row': row,
        'stage': stage,
        'admin_url': absolute_url(reverse('admin:survey_demorequest_change', args=[row.pk])),
    }
    return send_templated_mail('demo_request/notify', to, subject, context, fail_silently=fail_silently)


def emit(request, row, stage):
    """Send one `demo_requested` event. Never raises.

    A marketing signal about us, so PostHog -- never a `SurveyEvent`, which
    measures our customers' respondents on their behalf.
    """
    try:
        import posthog

        if posthog.disabled:
            return
        distinct_id = (
            str(row.user_id) if row.user_id
            else anonymous_distinct_id(request, f"demo_request_{row.pk}")
        )
        properties = {
            'stage': stage,
            'source': row.source,
            'authenticated': bool(row.user_id),
        }
        if stage == 'details':
            properties['timeline'] = row.timeline
        posthog.capture(DEMO_REQUESTED, distinct_id=distinct_id, properties=properties)
    except Exception:
        logger.warning('posthog: failed to emit %s', DEMO_REQUESTED, exc_info=True)
