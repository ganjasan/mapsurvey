## Context

Entitlements today are one function over one row: `billing.entitlements.for_organization(org)` reads the organisation's current `Subscription` (written only by the PayPro webhook) and the feature registry, and every gate — `require_feature`, `{% has_feature %}`, `api.gates.require_pro_api`, the badge switch in `SurveyHeaderForm`, `survey.ai.quota` — asks it. Pro is three features: `unbranded`, `pro_help`, `api`. There is no trial of any kind; `Subscription.trial_until` is PayPro's own trial field and both products are configured without one.

Issue #322 (academic programme) already asks for a second entitlement source, `EntitlementGrant`, next to the subscription. This change builds that model with the trial as its first kind, so #322 adds a kind and an admin form, not a mechanism.

Constraints: the Free plan is promised as "the whole product, not a trial" on six landings and the pricing FAQ, and the monetisation rules forbid gating surveys, responses, members, export or AI. A user can create any number of workspaces (`org_create`). Gunicorn workers are few and the API is called by agents in loops, so anything on the API path must be one cheap statement.

## Goals / Non-Goals

**Goals:**
- A workspace can use each of the three Pro features a fixed number of times within 90 days of claiming, with no card and no sales call.
- One mechanism (`EntitlementGrant` + `GrantAllowance`) that #322 reuses unchanged.
- Every "can this workspace do X" question keeps a single answer in `billing/entitlements.py`.
- The owner always knows where the trial stands and why a refusal happened.

**Non-Goals:**
- Any limit on Free (surveys, responses, members, export, AI generation).
- Automatic Pro or an automatic trial at registration.
- Trial e-mails (expiry, exhaustion) — the onboarding letters of #183.
- The academic grant's own flow (verification, admin form, programme page) — #322.
- Exposing the trial remainder through `/api/v1/me` or `get_me`; the 403 carries the state.

## Decisions

**D1. Two tables, not columns on `Organization` and not a JSON blob.**
`EntitlementGrant(organization, kind, claimed_by, granted_by, starts_at, expires_at, revoked_at, created_at)` and `GrantAllowance(grant, feature, limit, used)` with `unique(grant, feature)`. Columns on `Organization` would make the entitlement writable apart from the row that justifies it (the rule the feature registry docstring states); a JSON `{feature: {limit, used}}` cannot be incremented atomically under concurrent API calls. A partial unique constraint `unique(claimed_by) where kind='trial'` is the backstop for "one trial per user"; the claim function checks it first and renders a message, the constraint only stops a race.

**D2. A counter for every feature, no derived counts.**
`unbranded` counts switch-offs (True → False on a survey's `show_branding`), not surveys currently unbranded; `pro_help` counts stored requests; `api` counts gated calls. One `consume(org, feature)` path for all three: `UPDATE grant_allowance SET used = used + 1 WHERE grant_id = … AND feature = … AND used < limit` — one statement, race-free, `rowcount == 0` means exhausted. The alternative (count surveys with `show_branding=False` for `unbranded`) needs a rule for surveys unbranded under a lapsed Pro before the trial and a second code path; the counter has neither. Consequence to state on the page: a survey switched to unbranded during the trial stays unbranded until the trial expires, switching it back on refunds nothing.

**D3. Three questions: `has`, `may`, `covers`.**
`has(key)` keeps meaning "the plan includes the feature" — the plan cards, `is_pro`, the lapse task and the pricing page reason about the plan. `may(key)` = `has(key) or trial remaining for key > 0`: a NEW use is allowed. `covers(key)` = `has(key) or a live trial includes key`, spent or not: a state set earlier stays in force. Gates that decide an action move to `may`: `require_feature`, `require_pro_api`, `pro_organizations`, `SurveyHeaderForm.unbranded`. The `has_feature` template tag answers `covers`: both its callers (the badge partial and `public_results.html`) render the badge, and a survey switched off under the trial must stay unbranded after its one switch-off is spent — found by the expiry test during implementation, where `may` brought the badge back the moment the allowance hit zero. `Entitlements` gains `trial` (the live grant or `None`) and `allowances` (`{feature: Allowance(limit, used, remaining)}`). The viewer-dependent state (`none | available | live | exhausted | expired | used_elsewhere`) is computed by `billing/trial.py::state_for(org, user)`, not on the entitlements object, because "used elsewhere" depends on who is looking.

**D4. Consumption happens where the feature is used, after the gate says yes, only when the plan does not cover it.**
- `api`: inside `require_pro_api`: `has('api')` → return; else `consume(org, 'api')` → return on success, `pro_required` with `trial: 'exhausted'` (or `'expired'` / `'none'`) on failure. The check and the count are one statement, so there is no window between "may" and "used". A call that later 404s still counts — acceptable, the statement is the gate.
- `unbranded`: in `survey.services.surveys.update_settings` — the one write path for the editor's two settings views and the REST API — after the form is valid, inside the service's transaction: if the organisation does not `has('unbranded')` and `show_branding` goes True → False (`SurveyHeaderForm.consumes_unbranded()`), `consume`; on exhaustion (a form rendered while a switch-off was left, saved after) the form error on `show_branding` says the trial is used up and nothing is saved. Otherwise the switch is disabled once `may` is false, so a later switch-off is ignored like on Free. The switch stays enabled on a survey whose badge is already off, so the creator can always turn it back on.
- `pro_help`: in `org_help` before `req.save()`; exhausted → the Free view with the "used" message (the POST cannot normally reach there because the form is not rendered; a stale tab can).
A Pro workspace never consumes: the plan answers first. When Pro lapses and the trial is still live, the trial resumes with its remainder.

**D5. Claiming is one POST, owner only, four preconditions.**
`POST /org/<slug>/billing/trial/` (`org_billing_trial`): role `owner`; workspace not Pro (`has` on the plan); workspace has no grant of kind `trial`; the user has no trial grant anywhere. Creates the grant with `starts_at = now`, `expires_at = now + TRIAL_DAYS` and one allowance per entry of `TRIAL_ALLOWANCES`, emits `trial_claimed`, redirects to `?next=` when it is a safe local path (`url_has_allowed_host_and_scheme`), else to Plan & billing. The button appears on Plan & billing, on `feature_required.html` and on the Free view of the help page only in state `available`; the other states render their sentence instead (admins and editors see "ask the workspace owner").

**D6. Limits live in the registry, not in env.**
`billing/features.py`: `TRIAL_ALLOWANCES = {'api': 500, 'unbranded': 1, 'pro_help': 1}`, `TRIAL_DAYS = 90`. A feature absent from the dict is not in the trial; an empty dict means the trial is not offered (no button, claim endpoint 404) while grants already claimed keep working until they expire — the rollback story, same shape as `PPG_PRODUCTS` empty. Changing a number changes future claims only; existing allowance rows keep their `limit`.

**D7. Expiry is a comparison, not a cron.**
`for_organization` reads the grant with `revoked_at IS NULL AND starts_at <= now < expires_at` in one query with its allowances (`prefetch_related`), cached on the instance for the request like the subscription; `consume` clears that cache. No nightly task, no state flip, no e-mail — the same stance as subscription lapsing's access rule.

**D8. Refusals name the trial state.**
`feature_required.html` gets `trial_state` and renders: available → button; live but this feature exhausted → "Your Pro trial for this is used up"; expired → "Your Pro trial ended on <date>"; used elsewhere → "You used your Pro trial in <workspace>"; none/other role → today's text. The API error keeps code `pro_required` and adds `trial: "exhausted" | "expired" | "none"` to the envelope so an agent can tell its user why without a second call.

**D9. Events.** `trial_claimed` {org_id} on the owner; `trial_exhausted` {org_id, feature} once per feature, emitted by `consume` when the statement that reaches `used == limit` succeeds (the next call's `rowcount == 0` emits nothing), on the acting user when one exists (API: the token's user). Nothing on expiry.

## Risks / Trade-offs

- [One UPDATE per API call for trial workspaces] → only when the plan does not cover `api`; Pro workspaces pay nothing. An agent loop can burn 500 calls in minutes; the existing `mcp.session` cap (300 per 10 min) and the per-token minute windows bound the rate, and `get_me`'s description already tells agents the API is a Pro feature.
- [Many accounts, many trials] → one trial per user and per workspace; registration already has honeypot, rate limit and Turnstile. A determined person gets 500 calls per throwaway e-mail, which buys nothing worth the effort.
- [A survey unbranded under the trial regains the badge at expiry] → stated on Plan & billing and in the help page; this is the same behaviour as a lapsed subscription and the badge spec already requires it.
- [`has_feature` template tag changes meaning] → it answers `covers`, which is what both current callers (the badge) need; the tests for the badge and the tag cover a spent trial. New code that needs the plan uses `entitlements_for`; whether a new use is allowed is decided in views and forms.
- [One request may pass the Pro gate several times] → `require_pro_api` memoises the counted workspace on the request's `Principal`; `mcp.protocol.call_tool` clears it per tool call, so a JSON-RPC batch counts each call.
- [Trial card copy and the "Free plan, not a trial" promise] → the trial is a trial of the Pro extras, described only inside the product; no marketing template or `_plan_cards.html` bullet names it.
- [`claimed_by` user deleted] → `SET_NULL`; the grant keeps serving the workspace until expiry, and the partial unique index ignores NULL, so that user's successor could claim again — accepted, deleting an account is not an abuse vector worth code.

## Migration Plan

1. Migration `billing/000N_entitlement_grant.py`: two tables, no data, additive — safe in the pre-deploy window.
2. Deploy; nothing changes for existing workspaces until an owner clicks.
3. Rollback: empty `TRIAL_ALLOWANCES` hides the button and 404s the endpoint; claimed grants keep working until they expire; a full revert of the code leaves two unused tables, which a later migration drops.

## Open Questions

None blocking. The expiry / exhaustion letters go to #183; the academic kind goes to #322.
