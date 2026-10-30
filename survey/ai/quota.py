"""Quota seam for AI generation.

Permissive for every plan today: generation is login-gated only (an explicit
product decision, 2026-08-14). The entitlement lookup is real, though — since
the paywall (change paywall-payproglobal, #268) this is the ONE place a
per-plan generation limit is enforced: `generate_survey_draft()` calls
`check_quota()` before any provider call, so a quota block never spends a
token. The natural implementation is a count over `AIGenerationEvent` rows
per organization/window compared against a limit on the plan.

`kind` names what is being spent: `survey_draft` (one call set per draft) and,
since change paper-photo-entry (#495), `paper_page` — one vision call per
photographed page of a paper form, called from the worker before each call.
A per-plan allowance for pages is the pricing decision this seam waits for;
the hard bounds on a batch (`PAPER_BATCH_MAX_PAGES`) are sanity, not quota.
"""


class QuotaExceeded(Exception):
    """Raised when the organization has exhausted its generation allowance."""


def check_quota(organization, kind):
    """Precondition for every AI generation. Reads the plan; no plan has a limit yet."""
    from billing.entitlements import for_organization

    for_organization(organization)
    return None
