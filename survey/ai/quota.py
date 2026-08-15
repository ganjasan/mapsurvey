"""Quota seam for AI generation.

No-op in the MVP: generation is login-gated only (an explicit product
decision, 2026-08-14). When plans & entitlements land (#87), the real check
plugs in HERE and nowhere else — `generate_survey_draft()` already calls
`check_quota()` before any provider call, so a quota block never spends a
token. The natural implementation is a count over `AIGenerationEvent` rows
per organization/window compared against the org's plan.
"""


class QuotaExceeded(Exception):
    """Raised when the organization has exhausted its generation allowance."""


def check_quota(organization, kind):
    """Precondition for every AI generation. No-op until #87."""
    return None
