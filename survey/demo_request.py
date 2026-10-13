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


# Customer quotes for the /demo/ carousel (change demo-focus-page). Each is copied verbatim from
# the published story it links -- the story is the evidence, so never paraphrase here. A quote
# whose story is not published is not shown. `photo` is a static path, set only once the person
# has agreed to their picture being used; until then the card shows their initials.
# Deliberately not here: Julian Thomas's "completely free ... €4,500" line from the same story.
# It is the strongest price line we have, but on the page where people ask for a demo of the
# paid service it argues the wrong way.
DEMO_TESTIMONIALS = (
    {
        'text': (
            "Collecting quantitative data through a digital map at such an early stage allowed us "
            "to thoroughly prepare for qualitative workshop techniques, giving a voice to the people "
            "who use the bus station and market square every day and providing a solid foundation "
            "for further microplanning."
        ),
        'name': "Anna M. Pyziak",
        'role': "Secretary General",
        'organisation': "Towarzystwo Urbanistów Polskich",
        'story_slug': "pszow-microplanning",
        'story_label': "Read the Pszów story",
        'photo': "",
    },
    {
        'text': "I have to say, I am very impressed with the tool. It's intuitive, and has been very well-received.",
        'name': "Julian Thomas",
        'role': "Councillor",
        'organisation': "Whitehouse Community Council",
        'story_slug': "whitehouse-dog-bins",
        'story_label': "Read the Whitehouse story",
        'photo': "",
    },
    {
        'text': (
            "Thank you for getting this initiative started and the amazing results we now have in "
            "our possession: basically a survey and a workable outcome in one month, probably "
            "unheard of in local government."
        ),
        'name': "Cliff Schraibman",
        'role': "Parish Clerk and RFO",
        'organisation': "Whitehouse Community Council",
        'story_slug': "whitehouse-dog-bins",
        'story_label': "Read the Whitehouse story",
        'photo': "",
    },
)


def _initials(name):
    """'Anna M. Pyziak' -> 'AP': first and last word, so a middle initial never wins."""
    words = [w for w in name.replace('.', ' ').split() if w]
    return (words[0][0] + (words[-1][0] if len(words) > 1 else '')).upper() if words else ''


def live_testimonials():
    """The carousel's quotes whose story is published, in the order above."""
    from .models import Story

    live = set(Story.objects.filter(
        is_published=True, slug__in={t['story_slug'] for t in DEMO_TESTIMONIALS},
    ).values_list('slug', flat=True))
    return [dict(t, initials=_initials(t['name'])) for t in DEMO_TESTIMONIALS if t['story_slug'] in live]


# How many customer logos the strip under the form shows at most.
MAX_LOGOS = 8


def customer_logos():
    """Published stories that carry a credit logo, in the order the landing shows them."""
    from .models import Story

    qs = Story.objects.filter(is_published=True).exclude(credit_logo='').exclude(credit_logo__isnull=True)
    return list(Story.in_showcase_order(qs)[:MAX_LOGOS])


def page_context():
    """Everything the focused /demo/ layout needs besides the form: quotes and logos."""
    return {
        'testimonials': live_testimonials(),
        'logos': customer_logos(),
    }


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
