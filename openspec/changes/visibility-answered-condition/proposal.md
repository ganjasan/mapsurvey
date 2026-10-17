## Why

A visibility rule today means "the controller's answer is any of these option codes". The
common case — "show this once the respondent has answered the controller, whichever option" —
can only be written by ticking every option, and the list goes stale the moment the creator adds
an option: the new option shows nothing. In a pop-up that opens with a required "Type of place"
(#338), every other sub-question needs exactly this condition, so the stale-list trap is now the
normal path, not an edge (#339, epic #343).

## What Changes

- A second match mode on the rule: `{"question_code": "<controller>", "answered": true}` (no
  `choice_codes`). It matches when the controller has at least one selected choice. The
  existing shape keeps its meaning; `null` still means always shown.
- Engine: one branch in `survey/visibility.py` (verdict, match, describe, lint, client-rule
  shape); the respondent client toggles on "any value" for such rules. Applies wherever rules
  apply — questions, sections and pop-up sub-questions — because all of them go through the same
  verdict.
- Editor: in the Visibility block the "is any of" label becomes a select — *any of…* (the
  checkbox list, as today) / *answered (any option)* (list hidden, one line of help). The badge
  reads `if <controller> answered`; the modal pill and the Performance funnel label follow.
- An "answered" rule cannot break by option removal, and a section ruled this way covers every
  option of its controller in the uncovered-option lint.
- ZIP import accepts both shapes and normalises; export writes the stored rule as before, so an
  old archive is unaffected. Duplication and publishing already copy the rule dict verbatim.

## Capabilities

### Modified Capabilities
- `conditional-visibility`: rule model gains the "answered" match mode; broken-rule and lint
  requirements adjusted for it; editor authoring offers the mode.

## Impact

- `survey/visibility.py`, `survey/assets/js/conditional_visibility.js`, `survey/views.py`
  (client rules), `survey/editor_views.py` (`_parse_visibility_rule`, block context, preview
  rules), `survey/templates/editor/partials/_visibility_block.html`, `survey/serialization.py`
  (`_apply_visibility_rules`), `survey/analytics.py` (funnel eligibility for a section ruled
  "answered"), `survey/models.py` help texts (no migration: help_text only).
- Help article `how-to/make-a-question-conditional.md`. No changelog entry of its own: epic #343 gets one entry for all its changes.
- Depends on the unarchived `subquestion-visibility-rules` change (#338) for the sub-question
  host; its delta says a sub-question rule has "the same shape as a question rule", which stays
  true. Archive #338 first.
