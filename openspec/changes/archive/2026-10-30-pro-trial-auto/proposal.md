## Why

The Pro trial (#471) starts only when a workspace owner finds Plan & billing and clicks **Try Pro**, so most creators never touch a Pro feature; and nothing in the editor says which controls are Pro or that a trial covers them — a gated control is just disabled or refused. Issue #508.

Production data (2026-10-30, 48 creators whose first survey got ≥ 10 external answers): 90 % of the first survey's answers are in by day 10 / 37 / 57 after registration (p50 / p75 / p90); 96 % of creators reach that point within 90 days. `TRIAL_DAYS = 90` stays, and since the trial now starts at the first Pro use rather than at a click or at registration, it covers the survey that needs it.

## What Changes

- **The trial starts itself on the first Pro use.** When anyone authorised to make the use (an editor switching the badge off or entering a paper response, a member sending a help request, a token calling the API) does something the plan does not cover, in a workspace that has never had a trial and has an owner who has not used theirs, the trial is created for that workspace and the use is counted in the same transaction. The grant belongs to that owner (one trial per workspace owner, as today); the person who started it and the feature that started it are recorded. The **Try Pro** button stays as an explicit way in.
- **"May" includes "would start the trial".** Gated controls render enabled when the trial can start (badge switch, *Enter a response*, help form), so the first use is possible without a detour. **BREAKING** for the spec text "No trial SHALL be created at registration or by any other automatic path" — replaced.
- **Manual entry of paper responses starts the trial, without a cap** (owner decision 2026-10-30): `operator_entry` joins the trial with an uncapped allowance (`None`) — counted per entered session, never refused while the trial is live; the paper limit arrives with PDF and photo parsing (#495). Sessions entered under the trial stay after it ends.
- **One Pro mark, from the registry**: `{% pro_badge org "feature" %}` renders the same small mark next to every gated control in four states — plan (quiet "Pro"), trial ("Pro trial · N left"), can start ("Pro · free to try"), locked (lock + link to Plan & billing). Placed on the badge switch, *Enter a response*, the API & connections page and the Pro help entry points.
- **The trial tells people about itself**: the person whose use started it sees a one-time notice; the owner gets one e-mail when it starts (naming who started it and with what) and one 7 days before it ends, listing what stops. Nothing is sent when an allowance runs out (the refusal says it). **BREAKING** for "no e-mail SHALL be sent".
- **The help service gets a name that says what it is** (closes #438): `pro_help` is labelled "Advice on your survey and results" everywhere, the help page says what is included and that hands-on work is quoted; the menus list a free "Suggest an idea or report a bug" above it, so asking for features never looks like a Pro thing.
- **Events**: `trial_claimed` gains `trigger` (`click` or the feature key) and `auto`; `trial_ending_notified` on the reminder.

## Capabilities

### New Capabilities

_None_ — every requirement lands in an existing capability.

### Modified Capabilities

- `pro-trial-allowances`: claiming is no longer only the owner's click — automatic start on the first uncovered use; grant records who started it and why; start notice and ending reminder replace "ends quietly"; Plan & billing / refusal texts for the "can start" state.
- `plan-entitlements`: gate helpers answer "may, or would start the trial"; the `pro_badge` template tag as the one way to mark a Pro control.
- `operator-entry`: the control and entry URLs admit a startable workspace or a live trial; the first sheet starts the trial; sessions counted without a cap; the control carries the Pro mark.
- `pro-help-channel`: the form renders for members of a workspace whose trial can start; the first stored request starts it; the service is renamed and sits beside a free "Suggest an idea" entry.
- `api-pro-gate`: a call from a workspace whose trial can start starts it and is counted as its first call.

## Impact

- `billing/trial.py` (`startable`, `use`, auto-claim inside `consume`'s path), `billing/entitlements.py` untouched in its pure read; `billing/models.py` + migration (`EntitlementGrant.started_by`, `trigger`, `ending_notified_at`); `billing/features.py` (`operator_entry: None`, nullable `GrantAllowance.limit`), `billing/gates.py`, `billing/templatetags/billing_tags.py` (`pro_badge`), `billing/tasks.py` (start mail, daily ending reminder) + `notify_trials_ending` command in `reclaim.sh`; `billing/events.py`.
- Call sites: `survey/services/surveys.py` + `survey/editor_forms.py` (badge), `survey/operator_entry_views.py`, `survey/views.py` (`_upload_entry_session`), `survey/analytics_views.py`, `billing/views.py` (help), `api/gates.py`.
- Templates: settings badge switch, Responses v2 *Enter a response*, `api/connections.html`, help-menu/account-menu Pro help items, Plan & billing trial band, `feature_required.html`; mail templates; one CSS block.
- Strings in all ten offered catalogs; help centre `plans-and-billing.md` / `upgrade-to-pro.md`; the existing `2026-10-28-try-pro.html` changelog entry amended (one card per epic).
- No new dependency, no kill switch: an empty `TRIAL_ALLOWANCES` still turns every new trial off, automatic ones included.
