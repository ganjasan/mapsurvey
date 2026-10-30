## 1. Model and registry

- [x] 1.1 Add `started_by`, `trigger` (default `'click'`), `ending_notified_at` to `EntitlementGrant`; additive migration `billing/0003_…`
- [x] 1.2 `TRIAL_ALLOWANCES['operator_entry'] = None`; `GrantAllowance.limit` nullable (same migration); `UNIT_LABELS`/`UNIT_DETAILS` rows ("Paper responses entered")
- [x] 1.2a Uncapped allowances: `consume` UPDATE with `"limit" IS NULL OR`, `Allowance.remaining` None, `may` true, ignored for `exhausted`, meters show "N entered"
- [x] 1.3 Admin: show `started_by`, `trigger`, `ending_notified_at` read-only

## 2. Start-and-count core (`billing/trial.py`)

- [x] 2.1 Extract `_create_grant(org, owner, started_by, trigger, now)` from `claim()`; `claim()` records `trigger='click'`, `started_by=owner`
- [x] 2.2 `trial_owner(org)` (earliest-joined owner without a trial) and `startable(org, key)`, cached on the instance and cleared by `ents.forget`
- [x] 2.3 `may(org, key)` and `use(org, key, actor)` per design D2 (savepoint, IntegrityError fall-through, then `consume`)
- [x] 2.4 `trial_claimed` carries `trigger` and `auto`; add `TRIAL_ENDING_NOTIFIED` to `billing/events.py`
- [x] 2.5 `state_for`: `available` only when startable; live state exposes `started_by`/`trigger` for Plan & billing
- [x] 2.6 Tests (`billing/tests/test_trial_allowances.py`): auto start per feature, two owners, owner used elsewhere, race (two `use` calls → one grant, used=2), Pro never starts, empty registry never starts, rollback inside caller's transaction leaves no grant

## 3. Points of use

- [x] 3.1 `billing/gates.require_feature` decides on `trial.may`
- [x] 3.2 Badge: `SurveyHeaderForm` enables the switch on `trial.may`; `update_settings` calls `trial.use`
- [x] 3.3 Pro help: `org_help` decides on `trial.may`, counts with `trial.use`; startable sentence above the form
- [x] 3.4 API: `require_pro_api` calls `trial.use`; `pro_organizations` uses `trial.may`
- [x] 3.5 Operator entry: `entry_gate` on `trial.may`; `entry_header` POST calls `trial.use` before creating the session; `entry_section`/`entry_saved`/`_upload_entry_session` admit on `covers`; `analytics_views` passes `trial.may` + badge context
- [x] 3.6 Web uses add the one-time `messages.info` notice when `use` started the trial (check `editor_base.html` and `base.html` render messages)
- [x] 3.7 Update existing tests that expect a refusal for a grant-less Free workspace (api gate, pro help, operator entry, made-with badge) — make the fixture not startable or assert the start

## 4. Pro mark

- [x] 4.1 `{% pro_badge org "key" %}` inclusion tag + `billing/_pro_badge.html` + CSS in `css/pro_trial.css`, violet `--pro*` tokens (design D6)
- [x] 4.1a Recolour the Plan & billing trial band and the dashboard trial hero accents from teal to the `--pro*` tokens
- [x] 4.2 Place it: settings badge switch, Responses *Enter a response*, `api/connections.html`, Pro help items in the help menu and both account menus
- [x] 4.3 Tests: four states; hygiene test that gated controls use the tag

## 4b. Help service naming (#438)

- [x] 4b.1 `pro_help` label → "Advice on your survey and results" in `billing/features.py`; menu items in `base.html` and `editor/partials/_help_menu.html` use it with `pro_badge`
- [x] 4b.2 Free entry "Suggest an idea or report a bug" above it (support chat `topic: feature_request`, mail fallback)
- [x] 4b.3 Help page intro: what the advice covers, hands-on work quoted separately; pricing card / landing copy follow the label (no "reports included")
- [x] 4b.4 Tests: menu order and marks; label used on Plan & billing and `/pricing/`

## 5. Notices and mail

- [x] 5.1 `billing/tasks.py`: `send_trial_started(grant_id)` (on commit, click and auto) and `notify_trials_ending` (daily, 7-day window, once, skip Pro/revoked); run daily from `reclaim.sh` (`manage.py notify_trials_ending`)
- [x] 5.2 Mail templates `trial_started` / `trial_ending` (who started it and with what; what stops; nothing is deleted)
- [x] 5.3 Plan & billing trial band: "starts by itself" sentence for `available`; "started by X with Y" for `live`
- [x] 5.4 Tests: start mail names the editor; reminder once; none for Pro; none on exhaustion

## 6. Copy, docs, release

- [x] 6.1 New strings into all ten offered catalogs (`TranslationCatalogHygieneTest`)
- [x] 6.2 Amend `survey/changelog/2026-10-28-try-pro.html` (auto start)
- [x] 6.3 Help centre: `plans-and-billing.md`, `upgrade-to-pro.md` (trial auto start, new `pro_help` name)
- [x] 6.4 `CLAUDE.md` billing paragraph and `billing/README.md`: auto start, `trial.may`/`trial.use`, `pro_badge`
- [x] 6.5 Run `./run_tests.sh billing api survey` once after changes; fix and summarise
