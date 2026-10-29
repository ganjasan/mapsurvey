"""The feature registry: what a plan unlocks.

One entry per Pro capability. Adding a feature is adding a line here and gating
the code with `require_feature` / `{% has_feature %}` -- never a column on
`Organization`, which would make the entitlement writable apart from the
subscription that justifies it. Keys are stable strings used in templates and
PostHog properties; rename nothing, retire by deleting.
"""
from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

PLAN_FREE = 'free'
PLAN_PRO = 'pro'

PLAN_LABELS = {
    PLAN_FREE: _('Free'),
    PLAN_PRO: _('Pro'),
}


@dataclass(frozen=True)
class Feature:
    key: str
    plans: frozenset
    label: str


FEATURES = {
    # The "Made with Mapsurvey" badge finally honours SurveyHeader.show_branding
    # -- only for organisations that hold this.
    'unbranded': Feature('unbranded', frozenset({PLAN_PRO}),
                         _('Remove "Made with Mapsurvey" from your surveys')),
    # Pro is a service tier: the request form through which a Pro organisation
    # asks for consulting, analysis or a report.
    'pro_help': Feature('pro_help', frozenset({PLAN_PRO}),
                        _('Consulting, analysis and reports from the Mapsurvey team')),
    # Programmatic access (change auth-core, #379): the REST API, the MCP server
    # and what personal tokens or OAuth grants can reach. Checked at the
    # resource per request on the organisation that owns the object -- never
    # at token issue -- so a lapsed subscription stops access without
    # revoking anything and renewal brings the same token back.
    'api': Feature('api', frozenset({PLAN_PRO}),
                   _('REST API, MCP server and personal access tokens')),
    # The operator entry form (change operator-entry, #355): a workspace member
    # enters answers on someone's behalf -- paper sheets, assisted interviews,
    # field work. Checked on every entry request on the survey's organisation;
    # sessions entered while Pro stay when the subscription lapses.
    'operator_entry': Feature('operator_entry', frozenset({PLAN_PRO}),
                              _('Enter responses for others: paper forms, interviews, field work')),
}


# The Pro trial (change pro-trial-allowances, #471): not a period of Pro but a
# number of uses of each feature, valid for TRIAL_DAYS from the owner's click.
# A feature missing here is not part of the trial. An EMPTY dict means the trial
# is not offered at all (no button, the claim endpoint 404s) while grants that
# were already claimed keep serving until they expire -- the rollback. A new
# number applies to new claims only; a claimed grant keeps its own limits.
# AI generation is deliberately absent: it is free on every plan.
TRIAL_ALLOWANCES = {
    'api': 500,        # REST requests and MCP tool calls that pass the Pro gate
    'unbranded': 1,    # badge switch-offs (True -> False on a survey)
    'pro_help': 1,     # stored help requests
}
TRIAL_DAYS = 90


def features_for_plan(plan_code):
    return frozenset(key for key, f in FEATURES.items() if plan_code in f.plans)
