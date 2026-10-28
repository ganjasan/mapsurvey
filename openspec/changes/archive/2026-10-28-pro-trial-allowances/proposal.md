## Why

Pro has no trial: a workspace is Free until its owner pays, so a planner cannot see what the badge-free survey, the help channel or the API do for their project before putting Pro into a budget. The usual answer, 14 days of Pro after registration, does not fit this buyer — a participation project runs for weeks or months and a calendar trial expires before the first report. A trial measured in use (500 API calls, one survey without the badge, one help request), valid for 90 days from the day it is claimed, follows the project instead of the calendar. Issue #471; owner decision 2026-10-28: AI generation stays free for every plan, the trial covers exactly the three features in `billing/features.py`.

## What Changes

- **A second entitlement source.** `EntitlementGrant` (`kind='trial'`, later `'academic'` for #322) with one `GrantAllowance` row per feature (`limit`, `used`), read by `billing.entitlements.for_organization` next to the `Subscription`. The "one grant path" rule of the paywall change is deliberately widened: the webhook still owns `Subscription`; a grant is a different row with a different writer.
- **`Entitlements` gains `may(key)` and `allowances`.** `has(key)` keeps meaning "the plan includes it"; `may(key)` is "the workspace can use it now": the plan includes it, or a live trial has a remainder for it. Every gate that asks "can this workspace do X" (`require_feature`, the `has_feature` template tag, `require_pro_api`, `pro_organizations`, the badge switch in `SurveyHeaderForm`) moves to `may`; the plan cards and the lapse task keep `has`/`is_pro`.
- **Consumption is a counter for every feature**, incremented atomically: `api` on every REST request and MCP tool call that passes the Pro gate, `unbranded` each time a survey's badge is switched off, `pro_help` on every stored request. No derived counts.
- **Claiming is an owner's click**, "Try Pro", on Plan & billing, on `feature_required.html` and on the Free view of the help page — never automatic at registration. One trial per user, whichever workspace they claim it for; one trial per workspace.
- **Plan & billing shows the trial**: not yet claimed (what it contains), live (remainder per feature, expiry date), ended (expired or every allowance used). The refusal page and the API's `pro_required` error say which it is.
- **Expiry is passive**: after `expires_at` the badge renders again and tokens get `pro_required` on their next call; nothing is deleted, nothing is emailed (the "after the trial" letter belongs to the onboarding mail work, #183).
- Events `trial_claimed` and `trial_exhausted` (with `feature`), ids only. A changelog entry and a help page section ship with the change.
- **Nothing changes on the marketing site or on Free**: no limit on surveys, responses, members, export or AI, and the "Free plan, not a trial" copy stays.

## Capabilities

### New Capabilities
- `pro-trial-allowances`: the trial grant and its allowances — model, claim rules, atomic consumption, precedence of a paid plan, expiry, the Plan & billing card, the refusal messages, the registry of limits and the events.

### Modified Capabilities
- `plan-entitlements`: `for_organization` reads grants as well as subscriptions; the gating helpers consult `may` (plan or live allowance) instead of plan membership alone.
- `api-pro-gate`: the per-request check admits a live trial allowance for `api` and counts the call against it; an exhausted or expired trial is `pro_required` with the trial state named.
- `made-with-badge`: the badge honours a live trial like the entitlement; the branding switch is editable while the trial has a remainder and switching it off consumes one.
- `pro-help-channel`: the form opens for a workspace whose trial has a `pro_help` remainder; the stored request consumes it; the Free view offers the trial to the owner.

## Impact

- `billing/`: `features.py` (`TRIAL_ALLOWANCES`, `TRIAL_DAYS`), `models.py` + migration (two tables, no data), `entitlements.py`, `gates.py`, `templatetags/billing_tags.py`, new `trial.py` (claim, consume, state), `views.py`/`urls.py` (claim endpoint), `events.py`, `admin.py`, templates `org_billing.html`, `feature_required.html`, `org_help.html`.
- `api/gates.py` (`require_pro_api`, `pro_organizations`) — hence REST v1 and every MCP tool that goes through `api.v1.deps`.
- `survey/editor_forms.py` (`SurveyHeaderForm`), `survey/editor_views.py` (the two settings saves consume `unbranded`), `survey_settings.html` / `survey_settings_panel.html` hint text.
- Tests: new `billing/tests/test_trial_allowances.py`; `test_plan_entitlements.py`, `test_made_with_badge.py`, `test_pro_help_channel.py`, `api/tests` Pro-gate cases gain trial scenarios.
- `survey/changelog/<date>-try-pro.html`, `help/src/content/docs/how-to/upgrade-to-pro.md`, creator strings in every offered catalog, the Billing paragraph of `CLAUDE.md`.
- No change to PayPro, webhooks, checkout, `Subscription`, the marketing templates or the respondent pages beyond the badge rule.
