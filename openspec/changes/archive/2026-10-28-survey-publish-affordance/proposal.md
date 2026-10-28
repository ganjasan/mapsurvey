## Why

The Public results tab presents publishing as an obvious, consistent pair of context-bar buttons —
`Preview private` and a green `Publish page` — visible in every state. The Survey tab does not: its
context bar shows a green publish button only in the `draft` state. In `testing` the primary action
"Publish — open for responses" is buried inside the status-chip dropdown, and in `open`/`closed`
there is no action or state indicator in the bar at all — the whole lifecycle hides behind the
`Open · v1 ▾` chip in the top navbar.

The result is two different mental models for the same idea ("make this thing live"), and the
survey's own primary action — opening it for responses — is the least obvious of all, even though it
is the single most important thing a creator does. This change unifies the pattern: the Survey
context bar always shows `Preview` plus one primary action or state indicator, mirroring the
Public results tab.

## What Changes

- The Survey (Build) context bar SHALL always show, on the right, `Preview` plus a single primary
  element that reflects the survey's collection state:
  - `draft` → green **Publish** (unchanged behaviour — opens for responses)
  - `testing` → green **Publish — open for responses** (currently only reachable via the chip)
  - `open`/`published` → a **Live · Open** state indicator with an inline **Close** action
  - `closed` → a **Closed** state indicator with an inline **Reopen** action
- The rich lifecycle stays exactly where it is: the status chip (`_publishing_widget.html`) keeps
  Collection / Discovery / Results page / Version. This change surfaces the *primary* action, it does
  not move or duplicate the advanced controls.
- Draft-copy editing (`Publish Version` / `Discard`) is unchanged.
- **Non-goal**: no change to lifecycle states, transitions, permissions, or any server view. This is
  presentation over `survey.status`, reusing the existing `doTransition` / `showPublishConfirm` JS.

## Capabilities

### New Capabilities
- `survey-publish-affordance`: what primary publish/state control the Survey editor context bar shows
  for each survey status.

### Modified Capabilities

## Impact

- `survey/templates/editor/survey_detail.html` — the context bar (both the editable and the
  read-only/published branch) gains a state-driven primary action; reuses existing lifecycle JS.
- No new JS, no view change, no model change, no migration.
- Related to the recent `Publish` → `Public results` tab rename in `public-results-link-recovery`;
  this is the survey-side half of the same "make publishing legible" effort.
