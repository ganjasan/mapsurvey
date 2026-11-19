# Billing (PayPro Global) and the Pro trial

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Billing — Pro on PayPro Global (`billing/`, change `paywall-payproglobal`, #268)**: PayPro is the
Merchant of Record; we own the checkout link out (`billing/checkout.py`, the ONLY place a PayPro URL
is built, with `x-org_id/x-user_id/x-plan/x-nonce` and `ipn-domain`), the webhook in
(`POST /billing/ipn/` → `billing/ipn.py`: verify source IP + SHA256 `SIGNATURE` + MD5 `HASH` over the
RAW strings, store once in `BillingEvent`, apply the state machine to `Subscription`) and the
entitlement (`billing.entitlements.for_organization(org)` — Pro while `now < current_period_end` in
active/past_due/suspended/terminated, never after refund/chargeback/finish). **One grant path**: only
the webhook view writes `Subscription.status`/`current_period_end`; the return page polls, the
billing-page API actions (`billing/ppg.py`, shown only when `PPG_API_SECRET_KEY` is set) ask PayPro
and wait for the webhook. Features are the registry in `billing/features.py` (`unbranded`,
`pro_help`); gate with `require_feature` / `{% has_feature org "key" as x %}`, never a column.
`survey/ai/quota.py::check_quota` reads the same entitlement. `PPG_PRODUCTS` empty = nothing sold
(rollback). Test-mode webhooks are applied only where `PPG_ACCEPT_TEST_IPN` is true (previews). The
badge partial and `public_results.html` honour `show_branding` only under `unbranded`; the settings
form disables the switch otherwise. Setup checklist, env vars and the PayPro email:
`billing/README.md`. Reference digest of PayPro's docs lives outside the repo (local skill
`payproglobal`). Tests: `./run_tests.sh billing` — one module per capability, `billing/tests/test_<capability>.py` ↔
the spec of the same name (the rule proposed for `survey` in #273); payload and subscription
builders in `billing/tests/helpers.py`.

**Pro trial (change `pro-trial-allowances`, #471)**: the SECOND entitlement source, next to
`Subscription` — `EntitlementGrant` (`kind='trial'`; #322's academic grant is the next kind) with one
`GrantAllowance(feature, limit, used)` per feature. Not days of Pro but counted uses for
`TRIAL_DAYS` (90) after the OWNER's click (`POST /org/<slug>/billing/trial/`, `billing/trial.py::claim`):
`api` 500, `unbranded` 1, `pro_help` 1, `operator_entry` `None` = uncapped (counted, never refused;
the paper cap arrives with #495) (`TRIAL_ALLOWANCES` in `billing/features.py`; empty = not offered,
the rollback). One trial per OWNER (partial unique on `claimed_by`) and per workspace; never on Pro;
AI generation is not in it (free on every plan). **It starts itself (change `pro-trial-auto`, #508)**:
the first Pro use anyone allowed to make it makes in a workspace that never had a trial creates the
grant for the earliest-joined owner without a trial (`started_by` = the actor, `trigger` = the
feature key; a click is `trigger='click'`) and counts that use — never at registration or workspace
creation. Every control that OFFERS a use asks `billing.trial.may(org, key)` (= `Entitlements.may`
or `startable`), every point of use calls `billing.trial.use(org, key, actor)` (start + count),
never `consume` directly; the view then calls `trial.flash_started(request, org)` for the one-time
notice. The owner gets a start mail (on commit) and one "ends in 7 days" mail
(`notify_trials_ending`, daily from `reclaim.sh`, `ending_notified_at`). **Every Pro control carries
`{% pro_badge org "key" %}`** (`billing/_pro_badge.html`, `css/pro_badge.css`, violet `--pro`
tokens — teal is for actions): plan / trial / startable ("free to try") / locked; never hand-write a
Pro label. Navigation items (the sidebar) use `{% pro_nav_mark org "key" %}` instead (change
`onboarding-friction`, #638): nothing unless the workspace is `locked`, then a grey lock without the
word — a "PRO" in the sidebar read as "not for you" to the Free creators the trial is for. Tests that need a Free workspace REFUSED call `billing.tests.helpers.trial_used_elsewhere(org)`.
`pro_help` is "Advice on your survey and results" (#438), listed in every menu below a free "Suggest
an idea or report a bug" (`billing/_help_entries.html`). The webhook still owns
`Subscription`; a grant is a different row with a different writer. **Three questions on
`Entitlements`**: `has(key)` = the PLAN includes it (plan cards, `is_pro`, lapse task); `may(key)` = a
NEW use is allowed (plan, or a live trial's remainder) — wrapped by `trial.may`, which every gate
uses (`require_feature`, `require_pro_api`, `pro_organizations`, `SurveyHeaderForm.unbranded`);
`covers(key)` = in force (plan, or a live trial includes it, spent or not) — what `{% has_feature %}`
answers, because a survey unbranded under the trial stays unbranded after its one switch-off is
spent. A use the plan does not cover is counted ONLY by `trial.consume()` (through `trial.use`) — one
`UPDATE … WHERE ("limit" IS NULL OR used < "limit") RETURNING`, race-safe — at the point of use:
`require_pro_api` (once per request per workspace; `mcp.protocol.call_tool` resets the memo per tool
call), `services.surveys.update_settings` (a badge switch-off, inside the service transaction),
`org_help` (a stored request), `operator_entry_views.entry_header` (one sheet; the sheet's own pages
admit on `covers`). Expiry is a comparison, no cron. The viewer's state (`available | live | exhausted | expired |
used_elsewhere`) is `trial.state_for(org, user)`, rendered by `billing/_trial_offer.html`;
`pro_required` carries `trial: none|exhausted|expired`. Staff end a grant by setting `revoked_at` in
the admin; the counters are read-only there.
