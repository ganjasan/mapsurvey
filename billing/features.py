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
}


def features_for_plan(plan_code):
    return frozenset(key for key, f in FEATURES.items() if plan_code in f.plans)
