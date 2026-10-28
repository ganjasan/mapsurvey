## 1. Registry and model

- [x] 1.1 `billing/features.py`: add `TRIAL_ALLOWANCES = {'api': 500, 'unbranded': 1, 'pro_help': 1}` and `TRIAL_DAYS = 90` with a docstring stating that an empty dict means the trial is not offered and that a change affects new claims only
- [x] 1.2 `billing/models.py`: `EntitlementGrant` (`organization`, `kind` with choices `trial`, `claimed_by` SET_NULL, `granted_by` SET_NULL, `starts_at`, `expires_at`, `revoked_at`, `created_at`; partial `UniqueConstraint` on `claimed_by` where `kind='trial'`; `UniqueConstraint(organization, kind)`) and `GrantAllowance` (`grant`, `feature`, `limit`, `used`; `UniqueConstraint(grant, feature)`), with a module docstring paragraph on why a grant is a second writer next to the webhook
- [x] 1.3 Migration `billing/000N_entitlement_grant.py` (additive, no data); register both models in `billing/admin.py` (read-only counters, `revoked_at` editable for staff)

## 2. Entitlements, trial module, events

- [x] 2.1 `billing/entitlements.py`: `Allowance(limit, used, remaining)`; `Entitlements` gains `trial`, `allowances`, `may(key)`; `_compute` takes the live grant; `for_organization` loads the grant and its allowances in one query (prefetch) and caches as today; `has_feature` unchanged, new `may_feature(org, key)`
- [x] 2.2 `billing/trial.py`: `offered()`, `live_grant(org, now)`, `claim(org, user, now)` (four preconditions, returns the grant or raises a typed refusal naming the reason), `consume(org, feature, actor=None)` (one `UPDATE … WHERE used < limit`, `trial_exhausted` once on reaching the limit, clears `org._entitlements`), `state_for(org, user)` → `none | available | live | exhausted | expired | used_elsewhere` plus the grant and, for `used_elsewhere`, the other workspace
- [x] 2.3 `billing/events.py`: `TRIAL_CLAIMED = 'trial_claimed'`, `TRIAL_EXHAUSTED = 'trial_exhausted'` in `BILLING_EVENTS`

## 3. Gates move to `may`

- [x] 3.1 `billing/gates.py::require_feature` checks `may(key)` and passes `trial_state` (from `state_for`) to `feature_required.html`
- [x] 3.2 `billing/templatetags/billing_tags.py::has_feature` returns `may(key)`; docstring says so; add `trial_state_for(org, user)` tag for templates that render the offer
- [x] 3.3 `api/gates.py::require_pro_api`: `has('api')` → return; else `trial.consume(org, 'api', actor=principal.user)`; refusal adds `trial=<state>`; `pro_organizations` uses `may('api')`
- [x] 3.4 `survey/editor_forms.py::SurveyHeaderForm`: `self.unbranded = may_feature(org, 'unbranded')`; keep `disabled` logic; add `consumes_unbranded` (plan lacks it and the switch goes True → False) for the views
- [x] 3.5 `survey/services/surveys.py::update_settings` (the one write path of both editor settings views and the API): when `form.consumes_unbranded()`, call `trial.consume(org, 'unbranded', actor=actor.user)` before saving; on false add the form error on `show_branding` and raise `ValidationFailed`. The `has_feature` tag answers `covers` (badge render), found by the expiry test
- [x] 3.7 `api.gates.require_pro_api` counts one use per request per workspace (memo on the `Principal`); `mcp.protocol.call_tool` clears the memo so each call of a batch counts
- [x] 3.6 `billing/views.py::org_help`: gate on `may('pro_help')`; before `req.save()` consume when the plan lacks `pro_help`; the Free view receives `trial_state`

## 4. Claim endpoint and pages

- [x] 4.1 `billing/views.py::org_trial_claim` + `billing/urls.py` `org/<slug>/billing/trial/` (`org_billing_trial`): POST only, owner only, 404 when not offered, `claim()`, `trial_claimed`, safe `next` redirect, refusal reason as a message on Plan & billing
- [x] 4.2 `billing/templates/billing/org_billing.html`: trial block for non-Pro workspaces in the five states (available / live with "used N of M" per feature and the end date and the badge note / exhausted / expired / used_elsewhere); no block for Pro
- [x] 4.3 `billing/templates/billing/feature_required.html`: "Try Pro" form with `next` for the owner in state `available`; the state sentences otherwise
- [x] 4.4 `billing/templates/billing/org_help.html` Free view: the same control and sentences
- [x] 4.5 `survey/templates/editor/survey_settings.html` and `editor/partials/survey_settings_panel.html`: the disabled-switch hint links to Plan & billing and mentions the trial; render the `show_branding` form error

## 5. Tests

- [x] 5.1 `billing/tests/test_trial_allowances.py` (GIVEN / WHEN / THEN docstrings): claim rows and expiry date; once per user across workspaces; once per workspace; admin 403; Pro workspace refused; not offered → 404 and no control; `may` vs `has`; exhausted per feature; expired; `consume` atomic (two threads or two sequential calls with one left) and `trial_exhausted` once; Pro never consumes; lapse resumes the trial; Plan & billing block in each state; `feature_required.html` states; `next` redirect safety
- [x] 5.2 `billing/tests/test_plan_entitlements.py`: the three modified scenarios (no grant, live trial, exhausted via the template tag)
- [x] 5.3 `billing/tests/test_made_with_badge.py`: trial creator switches off once, second survey refused, badge returns at expiry
- [x] 5.4 `billing/tests/test_pro_help_channel.py`: trial member submits and the form closes; Free owner sees "Try Pro"
- [x] 5.5 `api/tests`: Pro-gate cases with a trial (counted down to `trial: "exhausted"`, `trial: "none"` on a Free workspace, Pro unchanged) and one MCP tool call counted
- [x] 5.6 Run `./run_tests.sh billing api mcp survey.tests.test_made_with_badge` (or the badge module's current name) once before and once after; summarise the delta

## 6. Strings, changelog, help, docs

- [x] 6.1 Add every new creator string to all offered catalogs by hand (as in PR #274) and compile; `TranslationCatalogHygieneTest` green
- [x] 6.2 `survey/changelog/2026-MM-DD-try-pro.html` (`kind: new`, `link: org_billing` is per-slug — use the account/billing entry the loader supports or omit `link`): what the trial contains and where to start it
- [x] 6.3 `help/src/content/docs/how-to/upgrade-to-pro.md`: a "Try Pro first" section (what is included, 90 days, the badge comes back at the end, one trial per person); `npm run build` in `help/` passes
- [x] 6.4 `CLAUDE.md` Billing paragraph: the second entitlement source, `may` vs `has`, where each feature consumes, `TRIAL_ALLOWANCES` empty as the rollback; `billing/README.md` ops note (admin: revoke a grant)

- [x] 6.5 Plan & billing band in the plan-card look (`billing/_trial_band.html`, `css/pro_trial.css`), tile details for every allowance
- [x] 6.6 Changelog entry as a dashboard hero: predicate `trial_available`, plate `art: trial`, `/billing/try-pro/`, `HERO_SPACING_EXCEPTIONS` row (owner: displace the assistant hero now)

## 7. Verify

- [x] 7.1 `/verify`: on the worktree's dev server claim the trial as an owner, switch a badge off, open the help form, make one API call with a personal token and watch the counter on Plan & billing; screenshots of the five block states where reachable
- [ ] 7.2 `openspec validate --strict pro-trial-allowances`; PR to `master` referencing #471 (no `[render preview]` unless asked)
