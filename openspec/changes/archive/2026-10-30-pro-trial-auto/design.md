## Context

`pro-trial-allowances` (#471, PR #474) shipped the trial as counted uses per feature for 90 days, claimed by the workspace owner's click (`billing.trial.claim`). Four gates count uses today:

| Feature | Gate (may) | Count (consume) |
|---|---|---|
| `unbranded` | `SurveyHeaderForm` disables the switch unless `ent.may` | `survey/services/surveys.update_settings` → `trial.consume` |
| `pro_help` | `billing/views.org_help` → `e.may` | same view → `consume` |
| `api` | `api/gates.require_pro_api`, `pro_organizations` | `require_pro_api` → `consume` |
| `operator_entry` | `require_feature` in `operator_entry_views.entry_gate`; `has_feature` in `analytics_views` and `views._upload_entry_session` | **nothing** — not in `TRIAL_ALLOWANCES` |

`EntitlementGrant` has `claimed_by` with a partial unique constraint (one trial per user) and `UniqueConstraint(organization, kind)`. `billing/entitlements.py` is a pure read (subscription + live grant, cached on the instance). Celery beat runs one task (`apply_survey_schedule`). Mail goes through `survey/mail.py::send_templated_mail`.

Owner decisions (2026-10-30): the trial starts at the first Pro action, not at registration or workspace creation; one trial per workspace owner; anyone allowed to make the use may start it; `TRIAL_DAYS = 90` stays (production data in the proposal).

## Goals / Non-Goals

**Goals:**
- One function decides "may this workspace make a new use" including "it would start the trial", and one function makes the use (start + count), so the four features cannot drift.
- Every gated control shows the same Pro mark in the same four states.
- The owner learns that a trial started on their behalf and that it is ending.

**Non-Goals:**
- Changing allowance sizes, `TRIAL_DAYS`, or the dashboard hero.
- A trial for workspaces that already had one (no reset, no second trial).
- Any change to `Subscription`, the webhook, checkout or AI quota.
- A cap on paper responses in the trial: it comes with PDF/photo parsing (`paper-photo-entry`, #495). Here manual entry starts the trial and is counted without a cap (D5).

## Decisions

### D1. `startable` and `use` live in `billing/trial.py`; `entitlements` stays pure
`Entitlements.may` keeps its meaning (plan or live remainder): it is cached per request and used by templates for state. "Would start" needs an owner lookup and is only needed where a NEW use is offered, so it goes into `trial.may(org, key)` = `ent.may(key) or startable(org, key)`. `startable` is cached on the organisation instance next to `_entitlements` and cleared by `ents.forget`.
*Alternative*: fold startable into `Entitlements`. Rejected — `for_organization` is called on every editor page (badge partial, AI quota); one more query for every Free page for a question only gates ask.

### D2. Start-and-count in one transaction; the constraint decides the race
`use(org, key, actor)`:
1. `ent.has(key)` → True.
2. live allowance → existing atomic `consume`.
3. `startable(org, key)` → inside `transaction.atomic()` (savepoint): create grant + allowances (`trigger=key`, `started_by=actor`, `claimed_by=first owner without a trial`); on `IntegrityError` (another request created it, or the owner's trial was taken elsewhere meanwhile) fall through; then `ents.forget(org)` and `consume`.
4. else False.
`claim()` (the click) and the auto path share one private `_create_grant(org, owner, started_by, trigger, now)`. Callers that already run inside `transaction.atomic` (`update_settings`) get a savepoint, so a refused save rolls back the grant too — a grant must not appear for a switch-off that was not stored.

### D3. Who the grant belongs to
`claimed_by` = the earliest-joined `owner` membership (`Membership.joined_at`, then id) whose user holds no trial grant. The constraint "one trial per user" stays the one rule. A workspace whose owners all used their trial elsewhere is not startable → locked mark, as before. *Alternative*: per-actor trial. Rejected by the owner ("one per workspace owner").

### D4. New fields, one migration
`EntitlementGrant.started_by` (FK user, null, SET_NULL), `trigger` (CharField 32, default `'click'`, existing rows `'click'`), `ending_notified_at` (DateTime null). Additive, safe in pre-deploy (no RemoveField — see the 2026-09 lesson).

### D5. `operator_entry`: starts the trial, counted, no cap
Owner decision 2026-10-30: manual entry of paper responses starts the trial like any Pro use, but has no limit inside it; the paper limit arrives with PDF/photo parsing (#495). Implemented as `TRIAL_ALLOWANCES['operator_entry'] = None` → `GrantAllowance.limit` NULL (migration: `limit` becomes nullable). `consume`'s UPDATE becomes `WHERE id = %s AND ("limit" IS NULL OR used < "limit")`, so uncapped uses are still counted (Plan & billing shows "N entered", the start event knows the feature). `Allowance.remaining` is `None` for uncapped; `may` treats `None` as available; `state_for` ignores uncapped rows when deciding `exhausted`. `entry_header` POST calls `trial.use` before creating the session; `entry_section`/`entry_saved` and `_upload_entry_session` admit on `covers`. When #495 sets a number, only new grants get it (existing rule).

### D6. One template tag for the mark
`{% pro_badge org "key" %}` (inclusion tag in `billing_tags`, template `billing/_pro_badge.html`, CSS in the existing `css/pro_trial.css`). State order: plan → trial (live remainder) → startable → locked. Text from `trial.unit_label`/registry. The gated control itself stays decided by `trial.may`; the badge only describes.

**Colour: violet, a Pro hue of its own** (owner decision 2026-10-30, after `pro-badge-colors.mockup.html`): `--pro: #6D4AE0`, `--pro-ink: #5A3BC4`, `--pro-soft: rgba(109,74,224,.11)`, `--pro-line: rgba(109,74,224,.35)`, defined once with the other tokens and used by the mark, the start notice and the Plan & billing trial band (recoloured from teal). Teal stays the colour of actions. White on `#6D4AE0` is 5.67:1 (AA for the 0.68rem label); teal (3.09) and gold (2.95) failed, and a filled teal "free to try" read as a second primary button. The locked state is grey whatever the hue.

### D7. Notices
- Actor notice: Django `messages` (`messages.info`) on web uses only; the API has no page — the owner mail covers it. Rendered by the existing messages block of `editor_base.html`/`base.html` (verify both render messages; add if not).
- Mail: `billing/tasks.py::send_trial_started(grant_id)` on commit (both click and auto); `notify_trials_ending` daily — a management command run from `reclaim.sh`, the daily Render cron that already runs `notify_lapsed`, so no beat process is needed — selects live, unrevoked grants with `expires_at` within 7 days and `ending_notified_at` null, skips Pro workspaces, sends, stamps. Templates `billing/email/trial_started.*`, `trial_ending.*`, English like the other billing mails (#437 covers billing translations).

### D8. Events
Keep `trial_claimed` (dashboards from #474 count it) and add properties `trigger` and `auto`; add `trial_ending_notified`. The issue said `trial_started`; reusing the shipped name keeps one funnel.

### D9. Changelog and help
Amend `survey/changelog/2026-10-28-try-pro.html` body ("starts by itself the first time you use any of them") and chips — one card per epic, no new hero (budget). Help: `plans-and-billing.md` trial section, `upgrade-to-pro.md`.

### D10. Name of the help service (closes #438)
Owner decision 2026-10-30: "Advice on your survey and results" replaces both the registry label "Consulting, analysis and reports from the Mapsurvey team" and the menu text "Pro help". "Ask the Mapsurvey team" was rejected: next to a Pro mark it reads as "asking for anything is paid", which discourages feature requests. A free "Suggest an idea or report a bug" entry (support chat with `topic: feature_request`, else mail) sits above it in the "?" menu and both account menus. The `ProHelpRequest.kind` choices stay (consulting / analysis / report / other); the help page's intro says hands-on work is quoted, matching the Done-for-you card.

## Risks / Trade-offs

- **An API script or an editor starts the owner's trial unnoticed** → owner mail at start names who and with what; Plan & billing shows it.
- **Existing tests assume a Free workspace without a grant is refused** (api gate, pro help, operator entry, badge form) → those fixtures must make the workspace not startable (owner with a trial elsewhere, or empty `TRIAL_ALLOWANCES` via `override_settings`-style patch) or assert the new start; expect a wide but mechanical test diff.
- **Extra query on gated paths for Free workspaces** (owner lookup) → cached per request; only on gate paths.
- **Grant created and save rolled back** → D2 savepoint inside the caller's transaction.
- **Beat task missed a day** → window is "within 7 days and not notified", so the next run catches up.

## Migration Plan

Additive migration in pre-deploy; deploy; the next daily `reclaim.sh` run sends the first reminders. Rollback: `TRIAL_ALLOWANCES = {}` stops every new trial (automatic included) without touching live grants; reverting the code leaves the three columns unused.

## Open Questions

- Should the start mail also go to the actor when it is not the owner? Proposed: no — they get the on-page notice.
