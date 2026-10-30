# pro-trial-allowances Specification

## Purpose
The free Pro trial: counted uses of each Pro feature (API and MCP calls, surveys without the badge, requests to the team) for TRIAL_DAYS after the workspace owner claims it -- the grant and allowance model, claim rules, atomic consumption at the point of use, has/may/covers, the Plan & billing band, refusals that name the trial state, and the dashboard hero for owners who can start it.
## Requirements
### Requirement: A trial is a grant with an allowance per feature
The system SHALL store a Pro trial as an `EntitlementGrant` row of `kind='trial'` with `organization`, `claimed_by` (the owner the trial belongs to), `started_by` (the person whose click or use started it, nullable), `trigger` (`click` or the feature key whose use started it), `starts_at`, `expires_at`, `revoked_at` and `ending_notified_at`, and one `GrantAllowance` row per feature with `feature`, `limit` and `used`, unique per grant and feature. The grant SHALL be the second entitlement source next to `Subscription`; nothing SHALL write `Subscription` on its account. A user SHALL hold at most one trial grant across all workspaces (enforced by a partial unique constraint on `claimed_by` for `kind='trial'`) and a workspace SHALL hold at most one.

#### Scenario: Claim creates the rows
- **WHEN** a trial is claimed for a workspace with `TRIAL_ALLOWANCES = {api: 500, unbranded: 1, pro_help: 1, operator_entry: None}` and `TRIAL_DAYS = 90`
- **THEN** one grant exists with `expires_at` 90 days after `starts_at`, `trigger = "click"`, and four allowance rows with `used = 0` and the registry limits (`operator_entry` with a null limit)

#### Scenario: Second claim by the same user elsewhere
- **WHEN** a user who already claimed a trial in workspace A owns workspace B and claims there
- **THEN** no grant is created for B and the response says the trial was used in A

### Requirement: Limits are declared in the feature registry
`billing/features.py` SHALL declare `TRIAL_ALLOWANCES` (feature key → limit, or `None` for a feature that is in the trial without a cap) and `TRIAL_DAYS`. Only features in the registry with a key in `TRIAL_ALLOWANCES` SHALL be part of a new trial. `operator_entry` SHALL be in the trial with `None` until a paper limit arrives with photo and PDF parsing. An uncapped allowance (`GrantAllowance.limit` null) SHALL be counted like any other but never refuse a use while the trial is live, and SHALL never make the trial `exhausted`. An empty `TRIAL_ALLOWANCES` SHALL mean the trial is not offered: no claim control renders, the claim endpoint answers HTTP 404 and no use starts a trial, while grants already created keep serving until they expire. Changing a limit SHALL affect new grants only.

#### Scenario: Trial not offered
- **WHEN** `TRIAL_ALLOWANCES` is empty and an owner of a Free workspace opens Plan & billing
- **THEN** no "Try Pro" control renders and `POST /org/<slug>/billing/trial/` returns HTTP 404

#### Scenario: Existing grant survives a registry change
- **WHEN** a grant was claimed with `api: 500` and the registry later says `api: 200`
- **THEN** the grant's allowance row still reads `limit = 500`

### Requirement: Claiming is an owner's explicit action
`POST /org/<slug>/billing/trial/` SHALL create the trial when the requester is the workspace `owner`, the workspace's plan is not Pro, the workspace has no trial grant and the requester has none in any workspace; otherwise it SHALL create nothing and answer HTTP 403 (role) or redirect with the reason shown on Plan & billing. A successful claim SHALL record `claimed_by = started_by = ` the owner and `trigger = "click"`, emit `trial_claimed` with `org_id`, `trigger: "click"` and `auto: false` on the owner, and redirect to a safe local `next` path when given, else to Plan & billing. No trial SHALL be created at registration or at workspace creation; the only other path is the first uncovered use. A GET SHALL be refused.

#### Scenario: Owner claims
- **WHEN** the owner of a Free workspace without a grant POSTs to the claim endpoint with `next=/editor/surveys/<uuid>/settings/`
- **THEN** a grant exists with `trigger = "click"`, `trial_claimed` was emitted once and the response redirects to that settings page

#### Scenario: Admin cannot claim
- **WHEN** an `admin` member POSTs to the claim endpoint
- **THEN** the response is HTTP 403 and no grant exists

#### Scenario: Pro workspace
- **WHEN** the owner of a workspace with an active subscription POSTs to the claim endpoint
- **THEN** no grant is created

#### Scenario: Registration creates nothing
- **WHEN** a person registers and their first workspace is created
- **THEN** no grant exists

### Requirement: `may` answers whether a feature can be used now
`Entitlements` SHALL expose `may(key)`, true when `has(key)` is true or when a live trial (`revoked_at` null, `starts_at <= now < expires_at`) has an allowance for `key` with `used < limit`; `covers(key)`, true when `has(key)` is true or a live trial has an allowance for `key` whatever its remainder; and `allowances` (feature → limit, used, remaining) plus `trial` (the live grant or `None`). `has(key)` SHALL keep meaning "the plan includes the feature". A new use SHALL be decided by `may`; rendering a state set earlier SHALL be decided by `covers`. `for_organization` SHALL read the grant and its allowances in one query and cache the result on the instance for the request as it does the subscription.

#### Scenario: Free with a live trial
- **WHEN** a Free workspace has a live trial with `api` used 10 of 500
- **THEN** `has('api')` is false, `may('api')` is true and `allowances['api'].remaining == 490`

#### Scenario: Allowance exhausted
- **WHEN** the trial's `pro_help` allowance reads `used == limit`
- **THEN** `may('pro_help')` is false while `may('api')` stays true and `covers('pro_help')` is true

#### Scenario: Trial expired
- **WHEN** `expires_at` has passed
- **THEN** `may(key)` is false for every feature and `trial` is `None`

### Requirement: Consumption is one atomic statement per use
`billing.trial.consume(organization, feature, actor=None)` SHALL increment `used` with a single `UPDATE … SET used = used + 1 WHERE … AND used < limit` on the live grant's allowance and return whether a row changed; a return of false SHALL mean exhausted or no live trial. When the update brings `used` to `limit`, it SHALL emit `trial_exhausted` with `org_id` and `feature` once, on the actor when one is known. `consume` SHALL clear the request-level entitlement cache of the organisation. A workspace whose plan includes the feature SHALL never consume.

#### Scenario: Concurrent last use
- **WHEN** two requests call `consume(org, 'api')` at the same moment with one call left
- **THEN** exactly one returns true, `used == limit`, and `trial_exhausted` is emitted once

#### Scenario: Pro does not consume
- **WHEN** a workspace is Pro and also holds a live trial and uses the API
- **THEN** the allowance's `used` is unchanged

### Requirement: Each feature consumes at its point of use
Each point of use SHALL call `billing.trial.use` (which starts a startable trial, see "The trial starts itself on the first uncovered use"). `api` SHALL consume once per REST request and per MCP tool call (each call of a JSON-RPC batch counting on its own) that passes `require_pro_api` for a workspace whose plan lacks `api`; a request that passes the gate several times for the same workspace SHALL count once. `unbranded` SHALL consume once each time a survey's `show_branding` changes from true to false through the survey settings service (`update_settings`, shared by the editor and the API); switching it back on SHALL refund nothing and a survey switched off during the trial SHALL stay unbranded until the trial ends. `pro_help` SHALL consume once per stored `ProHelpRequest`. `operator_entry` SHALL consume once per operator session created by the entry header (a startable workspace starts its trial there); the sections, the saved page and file uploads of a created session SHALL be admitted while the trial `covers` the feature, without consuming.

#### Scenario: Badge switched off twice
- **WHEN** a creator of a Free workspace with a live trial (`unbranded: 1`) switches the badge off on survey A, then submits B's settings with the badge unchecked
- **THEN** A is stored unbranded, B's switch is disabled and its submitted value ignored, and B keeps the badge

#### Scenario: Two tabs race for the last switch-off
- **WHEN** B's settings form was rendered while the switch-off was left and is saved after A spent it
- **THEN** the save is refused with an error on `show_branding` saying the trial for this is used up, and B keeps the badge

#### Scenario: Survey A switched back on
- **WHEN** the editor switches A's badge back on
- **THEN** `used` stays 1 and B still cannot be switched off

#### Scenario: Help request consumes
- **WHEN** a member of a Free workspace with a live trial submits a valid help request
- **THEN** the request is stored, `used == 1` for `pro_help`, and the page then renders the service description with "trial used" instead of the form

#### Scenario: Paper sheets are counted, not capped
- **GIVEN** a Free workspace with a live trial whose `operator_entry` allowance has a null limit and `used = 200`
- **WHEN** an editor submits the entry header and walks the session to the saved page
- **THEN** the session is stored and the allowance reads `used = 201`

#### Scenario: Paper entry closes with the trial
- **WHEN** the same trial expires
- **THEN** the entry header answers the feature refusal and the 201 sessions stay on Responses

### Requirement: A paid plan takes precedence and a lapse resumes the trial
While the workspace's plan includes a feature, the trial SHALL not be consulted or consumed. When the plan lapses and the trial is still live, `may` SHALL answer from the trial's remainder.

#### Scenario: Lapse during a trial
- **WHEN** a workspace claimed a trial, bought Pro, used the API 1000 times, and the subscription then lapsed within the trial's 90 days
- **THEN** `may('api')` is true with 500 remaining

### Requirement: Plan & billing shows the trial
Plan & billing SHALL render a trial block for a workspace whose plan is not Pro: state `available` → what the trial contains (each allowance with its limit and the number of days), the sentence that it starts by itself with the first use of any of them, and the "Try Pro" button for the owner (for admins, the same sentence without a button); `live` → per feature "used N of M" and "ends on <date>", who started it and with what, with the note that surveys made unbranded get the badge back then; `exhausted` (every allowance used) or `expired` → "Your Pro trial ended on <date>" with the Upgrade controls; `used_elsewhere` (the viewer claimed a trial in another workspace) → that sentence naming the workspace. A Pro workspace SHALL render no trial block.

#### Scenario: Live trial
- **WHEN** the owner opens Plan & billing with a live trial started by editor E with the badge switch-off, `api` used 120 of 500
- **THEN** the page shows "API: 120 of 500 used", the other allowances, the end date and that E started it by removing the badge

#### Scenario: Admin sees the offer
- **WHEN** an admin of a Free workspace without a grant opens Plan & billing
- **THEN** the trial block says the trial starts with the first Pro use and renders no button

### Requirement: The dashboard hero announces the trial to those who can start it
The changelog entry for the trial SHALL be a hero (`tier: hero`, plate `art: trial`) shown only
while the audience predicates `has_surveys` and `trial_available` hold: the viewer owns the
active workspace, which has at least one survey, is not on Pro, has had no trial, and the viewer
has claimed no trial anywhere. Its call to action SHALL be `billing_try_pro`
(`/billing/try-pro/`), which redirects to the active workspace's Plan & billing at `#pro-trial`.
The hero budget exception for this entry and the assistant hero two days before it SHALL be a
dated row in `HERO_SPACING_EXCEPTIONS` (owner decision 2026-10-28).

#### Scenario: Owner who can start it
- **WHEN** the owner of a Free workspace with a survey and no trial opens the dashboard
- **THEN** the trial hero is the pending hero and its button leads to the trial block of Plan & billing

#### Scenario: Others never see it
- **WHEN** the viewer is an admin of that workspace, or its owner after claiming, or the owner of a Pro workspace, or an owner who used their trial elsewhere
- **THEN** the trial hero is not shown

### Requirement: Refusals name the trial state
`feature_required.html` SHALL receive the viewer's trial state and render the "Try Pro" button (owner, `available`), or one sentence for `exhausted` (this feature's allowance used), `expired` (with the date) or `used_elsewhere` (the workspace), else today's text. The API's `pro_required` error SHALL carry `trial` with `"exhausted"`, `"expired"` or `"none"` next to `organization` and `upgrade_url`.

#### Scenario: Owner refused with a trial available
- **WHEN** the owner of a Free workspace without a grant opens the help page's form URL
- **THEN** the page offers "Try Pro" with the allowances listed, posting to the claim endpoint with `next` set to the page

#### Scenario: Token after exhaustion
- **WHEN** a token is used on a survey of a workspace whose trial `api` allowance is exhausted
- **THEN** the response is `403 {"error": "pro_required", "trial": "exhausted", …}`

### Requirement: The trial starts itself on the first uncovered use
A workspace SHALL be *startable* when the trial is offered (`TRIAL_ALLOWANCES` non-empty), its plan is not Pro, it holds no trial grant, the feature is in `TRIAL_ALLOWANCES`, and it has at least one `owner` member who holds no trial grant in any workspace. `billing.trial.may(organization, feature)` SHALL be true when `Entitlements.may(feature)` is true or the workspace is startable for the feature. `billing.trial.use(organization, feature, actor=None)` SHALL return true without counting when the plan includes the feature; consume one use of a live trial's allowance when there is one; and, when the workspace is startable, create the grant and its allowances and consume the first use in one transaction, then return true; else return false. The grant created this way SHALL have `claimed_by` = the workspace's owner without a trial who joined it first, `started_by` = the actor (whoever made the use; `null` for none), `trigger` = the feature key, `starts_at` = now and `expires_at` = now + `TRIAL_DAYS`. Two uses racing to start the same workspace's trial SHALL produce one grant and both uses SHALL be counted against it. Every point of use SHALL call `use` and every control that offers a use SHALL be decided by `may`; no other code path SHALL create a grant except the claim endpoint.

#### Scenario: An editor's first switch-off starts the owner's trial
- **GIVEN** a Free workspace with owner O (no trial anywhere) and editor E, and no grant
- **WHEN** E switches the badge off on a survey of the workspace
- **THEN** a trial grant exists for the workspace with `claimed_by = O`, `started_by = E`, `trigger = "unbranded"`, the `unbranded` allowance reads `used = 1`, and the survey is stored unbranded

#### Scenario: Owner already used a trial elsewhere
- **GIVEN** the workspace's only owner claimed a trial in another workspace
- **WHEN** an editor switches the badge off
- **THEN** no grant is created, the switch is disabled in the form, and a forced POST is refused on `show_branding`

#### Scenario: Two owners
- **GIVEN** owner A (joined first, trial used elsewhere) and owner B (joined later, no trial)
- **WHEN** the first uncovered use happens
- **THEN** the grant is created with `claimed_by = B`

#### Scenario: Concurrent first uses
- **WHEN** two API calls of a startable workspace arrive at the same moment
- **THEN** one grant exists and its `api` allowance reads `used = 2`

#### Scenario: Pro workspace
- **WHEN** a workspace with an active subscription uses the API
- **THEN** no grant is created

#### Scenario: Trial not offered
- **WHEN** `TRIAL_ALLOWANCES` is empty and an editor of a Free workspace without a grant opens survey settings
- **THEN** the badge switch is disabled and no grant can be created by any use

### Requirement: The trial announces its start and its end
When a trial starts through `use`, the actor, when it is a signed-in person on a web request, SHALL see a one-time notice on the next page naming the trial, its allowances and its end date. The owner (`claimed_by`) SHALL receive one e-mail per trial at its start — sent for automatic and clicked starts alike, naming who started it and with which feature when that was not the owner — and one e-mail 7 days before `expires_at`, listing what stops at the end (the badge comes back on surveys made unbranded, entry of paper responses closes, API and MCP calls answer `pro_required`, the help form closes) and that no answer, survey or token is deleted. The reminder SHALL be sent by a daily periodic task at most once per grant (`ending_notified_at`), never for a revoked grant or a workspace that is Pro at that moment. No e-mail SHALL be sent when an allowance runs out. After `expires_at`, or for a feature whose allowance is exhausted, the workspace SHALL be treated as Free for that feature: the badge renders again on surveys with `show_branding=False`, tokens get `pro_required` on their next call, the help form and the entry of paper responses close; nothing SHALL be deleted or rewritten. Mail goes through the shared templated-mail helper, one Celery task per message, after commit.

#### Scenario: Start mail names the editor
- **WHEN** editor E starts owner O's trial by switching the badge off on a survey
- **THEN** O receives one e-mail saying E started it by removing the badge, listing the allowances and the end date, and E sees the notice on the next page

#### Scenario: Reminder once
- **GIVEN** a live grant expiring in 6 days with `ending_notified_at` null
- **WHEN** the periodic task runs twice
- **THEN** the owner receives one e-mail and `ending_notified_at` is set

#### Scenario: No reminder for a Pro workspace
- **GIVEN** the workspace bought Pro during its trial
- **WHEN** the task runs 7 days before `expires_at`
- **THEN** no e-mail is sent

