## ADDED Requirements

### Requirement: The Survey context bar always shows a primary publish action
For a survey owner, the Survey (Build) editor context bar SHALL always present, on the right, a `Preview` control plus a single primary control that reflects the survey's collection status, so that publishing is as obvious on the Survey tab as on the Public results tab. The control SHALL be driven by `survey.status` and SHALL reuse the existing transition handlers; no new lifecycle state, transition, or endpoint is introduced.

- `draft` — a primary **Publish** action that opens the survey for responses.
- `testing` — a primary **Publish — open for responses** action (the same one otherwise reachable only through the status chip).
- `published`/`open` — an **Open** state indicator with an inline **Close** action.
- `closed` — a **Closed** state indicator with an inline **Reopen** action.

A draft-copy under edit is exempt: it keeps its `Publish Version` / `Discard` actions, which publish a version rather than change collection status.

#### Scenario: Draft shows Publish
- **WHEN** the owner opens the Survey tab of a survey in `draft`
- **THEN** the context bar shows `Preview` and a primary `Publish` action

#### Scenario: Testing surfaces the primary publish action
- **WHEN** the owner opens the Survey tab of a survey in `testing`
- **THEN** the context bar shows a primary `Publish — open for responses` action, not only the status chip

#### Scenario: Open shows state and a Close action
- **WHEN** the owner opens the Survey tab of a `published` survey
- **THEN** the context bar shows an `Open` state indicator and an inline `Close` action

#### Scenario: Closed shows state and a Reopen action
- **WHEN** the owner opens the Survey tab of a `closed` survey
- **THEN** the context bar shows a `Closed` state indicator and an inline `Reopen` action

#### Scenario: Draft-copy keeps its version actions
- **WHEN** the owner edits a draft copy
- **THEN** the context bar keeps `Publish Version` and `Discard`, and does not show the collection-status primary action

### Requirement: The primary action is owner-only and presentation-only
The primary-action control SHALL render only for `effective_role == 'owner'` on a non-archived survey, matching the status chip's guard; other roles SHALL continue to see only `Preview`. The control SHALL NOT change permissions, views, models, or introduce a migration — it reads `survey.status` and calls the existing `doTransition` / `showPublishConfirm` handlers.

#### Scenario: Non-owner sees only Preview
- **WHEN** a user whose effective role is below owner opens the Survey tab
- **THEN** the context bar shows `Preview` but no publish/close/reopen action

#### Scenario: The advanced lifecycle stays in the status chip
- **WHEN** the owner opens the status chip
- **THEN** it still offers Collection / Discovery / Results page / Version, unchanged by this control
