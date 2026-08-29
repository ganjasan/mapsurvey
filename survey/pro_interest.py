"""The Pro early-access questionnaire — options, and the event it emits.

This module is the single source of truth for what `/pro/` asks. The template
renders from `CAPABILITY_GROUPS`, `ProInterestForm` validates against
`CAPABILITY_KEYS`, and `ProInterest.capabilities` stores those same keys. A
checkbox that existed in the template but not here would be dropped on save
without an error, which would quietly corrupt the only dataset the page exists
to collect -- so there is one list and everything reads it.

Keys are stable strings, never positions. Reordering an option or inserting one
must not change the meaning of rows already stored, because the whole point is
comparing what different segments ticked over time.

Adding an option is additive: append it, and older rows simply never carry the
key. Never reuse a retired key for a different capability.
"""

import json
import logging

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

PRO_INTEREST_SUBMITTED = 'pro_interest_submitted'

# Who is answering. A field on the answer, not a routing decision -- the page
# deliberately shows every group to everyone so that cross-segment surprises
# (a city ticking "resell", say) stay visible instead of being designed away.
SEGMENT_CHOICES = (
    ('public_body', _("City, district or public body")),
    ('consultancy', _("Consultancy or agency")),
    ('ngo', _("NGO or community group")),
    ('research', _("University or research")),
    ('other', _("Something else")),
)

# Where the money would come from. Deliberately not "how much would you pay":
# that question is answered with silence or with a lie, while this one is
# answered readily and settles what actually blocks a price -- per project or
# per year.
BUDGET_SHAPE_CHOICES = (
    ('project_grant', _("A project or grant budget")),
    ('annual_software', _("An annual software budget")),
    ('billed_to_client', _("Billed on to our client")),
    ('no_budget', _("There is no budget")),
    ('unknown', _("No idea yet")),
)

# Capabilities, grouped by the outcome a visitor is after rather than by the
# audience that wants them. Grouping by audience would mean deciding in advance
# what each audience buys, which is the question we are asking. Every group is
# shown to everyone.
CAPABILITY_GROUPS = (
    {
        'key': 'make_it_yours',
        'label': _("Make it yours"),
        'options': (
            ('own_domain', _("Your own domain and branding"),
             _("The survey looks like yours, not ours")),
            ('white_label', _("Remove Mapsurvey from the page entirely"),
             _("White-label, nothing points back to us")),
        ),
    },
    {
        'key': 'public_results',
        'label': _("Show results in public"),
        'options': (
            ('live_map', _("Live public map of what people submitted"),
             _("Updates as responses come in")),
            ('moderation', _("Moderation before anything appears"),
             _("You approve each contribution")),
            ('voting', _("People vote on each other's points"),
             _("Agree / disagree, or a simple upvote")),
            ('comments', _("Comments and discussion on the map"),
             _("Replies under a marked place")),
        ),
    },
    {
        'key': 'get_answers',
        'label': _("Get people to answer"),
        'options': (
            ('qr_posters', _("Print-ready QR posters and flyers"),
             _("For noticeboards, events, site visits")),
            ('tracked_links', _("A tracked link per channel"),
             _("See which channel actually worked")),
            ('dropoff', _("Where people dropped off"),
             _("Which question loses them")),
            ('outreach_help', _("Help planning the outreach itself"),
             _("Not software — us, working with you")),
        ),
    },
    {
        'key': 'handover',
        'label': _("Hand over the result"),
        'options': (
            ('report', _("A report you can give a council or funder"),
             _("Map, charts and a written summary")),
            ('shapefile_qgis', _("Shapefile and QGIS export"),
             _("On top of GeoJSON and CSV")),
            ('analysis_by_us', _("Analysis done by us"),
             _("You get conclusions, not a spreadsheet")),
        ),
    },
    {
        'key': 'multi_project',
        'label': _("Run more than one project"),
        'options': (
            ('many_clients', _("Several clients or areas in one account"),
             _("Kept apart, with their own access")),
            ('templates', _("Reusable templates"),
             _("Start the next one from the last one")),
            ('roles', _("Colleagues on the same project, with roles"),
             _("Who can edit, who can only read")),
            ('resell', _("Resell it to your own clients"),
             _("Under your name, on your terms")),
        ),
    },
    {
        'key': 'paperwork',
        'label': _("Satisfy the paperwork"),
        'options': (
            # Listed as a candidate, and phrased as one. Production runs in the
            # US; the page must never read as though EU hosting already exists.
            ('eu_hosting', _("Choose EU or US hosting"),
             _("Decided per project")),
            ('dpa', _("Signed DPA / AVV"),
             _("With sub-processors documented")),
            ('accessibility', _("Accessibility statement (BITV / WCAG)"),
             _("For the survey your audience uses")),
            ('self_host', _("Run it on your own servers"),
             _("Self-hosted, with us keeping it running")),
            ('invoice', _("An invoice, not a card payment"),
             _("PO, bank transfer, VAT ID")),
            ('security_questionnaire', _("Answers to a security questionnaire"),
             _("For your IT department")),
        ),
    },
)

CAPABILITY_KEYS = frozenset(
    option[0] for group in CAPABILITY_GROUPS for option in group['options']
)


class ProInterestForm(forms.Form):
    """Validates one `/pro/` submission.

    Two rules carry the design: an empty capability selection is valid (see
    `ProInterest`), and an unknown capability key is a hard error rather than a
    silently ignored value -- a key we cannot explain means the template and
    this module have drifted, and dropping it quietly is how the dataset would
    rot without anyone noticing.
    """

    email = forms.EmailField(
        label=_("Your email"),
        error_messages={'required': _("We need an email to write back to.")},
    )
    organisation = forms.CharField(
        label=_("Organisation"), max_length=200, required=False,
    )
    segment = forms.ChoiceField(
        label=_("What kind of work do you do?"),
        choices=SEGMENT_CHOICES, required=False,
    )
    capabilities = forms.MultipleChoiceField(
        label=_("Which of these would actually matter to you?"),
        choices=[
            (option[0], option[1])
            for group in CAPABILITY_GROUPS for option in group['options']
        ],
        required=False,
        error_messages={
            'invalid_choice': _("That is not an option we offer on this page."),
        },
    )
    missing_text = forms.CharField(
        label=_("What did we miss?"), required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    budget_shape = forms.ChoiceField(
        label=_("If you paid for this, where would the money come from?"),
        choices=BUDGET_SHAPE_CHOICES, required=False,
    )
    consent = forms.BooleanField(
        label=_("You may store this and email me about it."),
        required=True,
        error_messages={
            'required': _("We can only store your answer if you agree to it."),
        },
    )

    def save(self, user=None):
        """Create the `ProInterest` row. Call only on a valid form."""
        from .models import ProInterest

        data = self.cleaned_data
        return ProInterest.objects.create(
            email=data['email'],
            organisation=data.get('organisation', ''),
            segment=data.get('segment', ''),
            capabilities=list(data.get('capabilities') or []),
            missing_text=data.get('missing_text', ''),
            budget_shape=data.get('budget_shape', ''),
            user=user if (user is not None and user.is_authenticated) else None,
            consent_at=timezone.now(),
        )


def _anonymous_distinct_id(request, interest):
    """A distinct id for an anonymous submitter. Never None.

    Preference order matters. The browser snippet keeps its device id in a
    `ph_<key>_posthog` cookie, so reusing it makes the submission land on the
    same person as their `$pageview`s -- the difference between "someone
    submitted" and "the visitor who read the whole page submitted". The session
    key is second best: it groups one visitor's events without tying them to
    the pageview stream.

    The row-id fallback exists because the first two are routinely absent: an
    ad blocker stops the snippet from ever writing a cookie, and Django has no
    session key until something writes to the session. Returning None there
    would silently drop the event for exactly the anonymous majority the page
    is built to hear from -- so every stored answer gets counted, even when it
    cannot be stitched to a person.
    """
    for name, value in request.COOKIES.items():
        if not (name.startswith('ph_') and name.endswith('_posthog')):
            continue
        try:
            distinct_id = json.loads(value).get('distinct_id')
        except (ValueError, AttributeError):
            continue
        if distinct_id:
            return str(distinct_id)
    if request.session.session_key:
        return f"anon_session_{request.session.session_key}"
    return f"pro_interest_{interest.pk}"


def emit_pro_interest(request, interest):
    """Send one `pro_interest_submitted` event. Never raises.

    Separate from `product_events.emit` on purpose: that module is the creator
    lifecycle funnel and every event in it must be reconstructable from an
    existing timestamp. This is a marketing-research signal, and it also has to
    work for a visitor with no user account, which `emit` refuses by design.

    This measures *us* -- which creator-facing offer people want -- so PostHog is
    the right home. It must never be written as a `SurveyEvent`: that system
    measures our customers' respondents on their behalf.
    """
    try:
        import posthog

        if posthog.disabled:
            return
        distinct_id = (
            str(interest.user_id) if interest.user_id
            else _anonymous_distinct_id(request, interest)
        )
        posthog.capture(
            PRO_INTEREST_SUBMITTED,
            distinct_id=distinct_id,
            properties={
                'segment': interest.segment,
                'capabilities': list(interest.capabilities or []),
                'capability_count': len(interest.capabilities or []),
                'budget_shape': interest.budget_shape,
                'has_missing_text': bool(interest.missing_text),
                'authenticated': bool(interest.user_id),
            },
        )
    except Exception:
        logger.warning('posthog: failed to emit %s', PRO_INTEREST_SUBMITTED,
                       exc_info=True)
