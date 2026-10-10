## Why

PostHog keeps showing the same leak: creators open a published survey, try to change something, and
do not get past "Published and closed surveys cannot be edited — Draft new version". The model
behind that message (a published survey is frozen; you fork a *draft copy*, edit the copy, publish
it as a *version*) is correct engineering and the wrong product surface:

- **The lock is total, the risk is not.** `_check_structural_edit_allowed` refuses every edit on a
  `published`/`closed` survey. But the only edits that can hurt collected answers are the three that
  `check_draft_compatibility` already names: deleting an answered question, changing an answered
  question's type, removing an answered choice. Fixing a typo, rewording help text, adding a
  translation or an option, nudging the start map — none of these orphan anything, and they are
  what people are trying to do when they hit the lock.
- **Every fix costs a version.** `publish_draft` archives the old structure and moves all sessions
  onto it, so one typo fix splits the survey's data into v1 and v2. Creators who do find the route
  then meet versions in Responses and exports for a change they consider trivial.
- **The draft is a second survey.** It has its own UUID, a "Draft of …" title, its own URL, its own
  Responses scope, and it is reached through "Draft new version" / "Go to draft" / "Publish
  Version". On desktop the disabled form gives no explanation at all when clicked (only mobile has
  the `editIntercept` sheet).

The concept users need is the one every CMS teaches: *the live survey; edits that are safe go live;
bigger edits wait as unpublished changes until you publish them.*

## What Changes

Two layers. Layer 1 removes most encounters with the draft; layer 2 renames and flattens what is
left.

### Layer 1 — safe edits apply to the live survey in place

- A published or closed survey's Build page is editable. Edits that cannot orphan a collected answer
  save directly to the live survey, with no draft and no new version: question/section text,
  help text and translations, choice labels, *adding* choices, required/validation settings, map
  start position/zoom/basemap, icons and colours, the thanks page and survey settings.
- One classifier, `versioning.classify_live_edit(...)`, decides per request whether an edit is
  **safe** or **structural**, from the same rules `check_draft_compatibility` uses, so the editor and
  the publish check can never disagree. It replaces `_check_structural_edit_allowed`.
- A live save shows a quiet "Saved · live" in the autosave indicator. Rewording an answered question
  shows a one-line hint that respondents who already answered saw the old wording (no block).

### Layer 2 — structural edits become "unpublished changes", not a second survey

- Structural edits (add/delete/reorder questions or sections, change a type, remove an answered
  choice, edit visibility rules) on a live survey are not refused. The first one asks once, inline:
  "This changes the structure of a live survey. Your edits will be kept as unpublished changes until
  you publish them — respondents keep seeing the current version." → *Start editing*. That creates
  the draft copy (existing `clone_survey_for_draft`) and replays the action into it.
- Vocabulary everywhere: "Draft new version" / "Go to draft" / "Draft of X" / "Publish Version" /
  "Discard draft" → **Edit** / **Unpublished changes** / **X** (with an "Unpublished changes" pill) /
  **Publish changes** / **Discard changes**. "Version" appears only in Responses and exports, where
  it describes data.
- One place to edit: opening Build on a survey that has unpublished changes lands on them; the live
  page is reachable as "View live version". The dashboard card shows an "Unpublished changes" badge
  instead of nothing.
- Desktop gets the intercept mobile already has: clicking a control that still cannot be used
  explains why and offers the action, instead of a dead disabled field.

### Measuring it

- New product events (`pe`): `live_edit_saved {kind: question|section|map}`,
  `unpublished_changes_started {then}`, `unpublished_changes_published`,
  `unpublished_changes_discarded`, and `structure_gate_shown {action}` from the browser.
  Success = drop in creators who open a published survey's Build page, click an editing control and
  leave without a saved edit, compared over the four weeks before and after.

## Non-goals

- No change to what counts as breaking, to `publish_draft`'s archive-and-move, to cross-version
  analytics or to exports.
- Not letting a survey with responses go back to `draft` (unchanged from `closed-survey-edit-path`).
- No change to the respondent page.

## Capabilities

### New Capabilities
- `live-survey-editing`: which edits apply to a live survey in place, how structural edits become
  unpublished changes, and the vocabulary the editor uses for them.

### Modified Capabilities
- `survey-edit-recovery` (from `closed-survey-edit-path`): the read-only banner is replaced by the
  editable Build page; its "always ends in an action" rule is kept for the intercept.

## Impact

- `survey/versioning.py` — `classify_live_edit`, shared with `check_draft_compatibility`.
- `survey/editor_views.py` — `_check_structural_edit_allowed` → classifier; question/section/settings
  save views accept safe edits on live surveys; `editor_survey_detail` redirect to unpublished
  changes; structural-edit endpoint that creates the draft and replays.
- Templates: `survey_detail.html` ctx-bar and mobile status bar, `_survey_title.html`,
  `_publishing_widget.html`, `_survey_primary_action.html`, dashboard card, question/section forms.
- `survey/product_events.py` — the events above. New strings are English only for now (design: Translations).
- No migration.
