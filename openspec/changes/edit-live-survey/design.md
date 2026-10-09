## Context

Today: `status in ('published','closed')` ⇒ `is_read_only` ⇒ every editing view returns 403 through
`_check_structural_edit_allowed`, and the template disables every control. The only way out is
`editor_create_draft` → a separate `SurveyHeader` (`published_version` FK) → `editor_publish_draft`
→ `publish_draft()` archives the canonical structure and its sessions as version N and moves the
draft's sections onto the canonical.

## Decisions

### D1. Safe vs structural is decided per edit, on the server, by one function

`classify_live_edit(survey, model, instance, new_values) -> 'safe' | 'structural'`.

Structural (needs unpublished changes):
- create/delete/reorder/paste a question or section, change `next_section`;
- change `input_type`, `parent_question`, `layer` binding, `code`;
- remove a choice code that has answers (removing an unanswered choice is safe — same rule as
  `check_draft_compatibility`, which already only counts answered codes);
- change a `visibility_rule` (it changes who is asked what mid-collection).

Everything else on `Question`, `SurveySection`, their translations and `SurveyHeader` settings is
safe. The view computes the diff between the posted form's `cleaned_data` and the stored row, so a
form that posts every field still classifies by what actually changed.

Why not allow structural edits on unanswered questions in place too: possible, but it makes the
rule depend on live data that changes under the creator ("why could I delete this yesterday?").
A rule by *kind of edit* is explainable in one sentence. Revisit if data says otherwise.

### D2. Wording changes are allowed live, with a hint, not a block

Changing the text of an answered question can change what earlier answers mean. That is the
creator's call — they are the only one who knows whether it is a typo or a new question. We show
"N people already answered the previous wording" once under the field, and record nothing new.
Not versioning wording is also what keeps the data from splitting into v1/v2 over a typo.

### D3. Unpublished changes reuse the draft copy, renamed

The draft copy model, `clone_survey_for_draft`, the compatibility check and `publish_draft` stay as
they are; what changes is when the draft is created (on the first structural edit, after one
inline confirmation) and how it is presented. The structural action that triggered it is replayed
into the draft by mapping the section/question by `code` (codes are preserved by the clone), so the
creator's click is not lost. If replay fails (e.g. the target no longer maps) we land them on the
same section in the draft with the action not applied and say so.

### D4. One editing surface per survey

`editor_survey_detail` on a canonical survey that has a draft copy redirects to the draft unless
`?live=1`. The draft page carries the live survey's name (no "Draft of" prefix; the `[draft]`
stored name stays for admin/back-compat but is never rendered) plus an "Unpublished changes" pill
and a "View live version" link. Results/Share/Public-results tabs on the draft keep pointing at the
canonical (already the case via `canonical_of`).

### D5. Safe edits while unpublished changes exist

If a draft exists, *all* Build edits go to the draft (one editing surface, D4). A safe edit then
waits for "Publish changes" like any other. Simpler than splitting an edit stream across two rows;
the pill makes it visible.

## Risks

- A creator rewords a question into a different question (D2). Mitigation: the hint; the
  compatibility check still catches type changes and removed answered choices.
- Respondents mid-session see changed wording on the next section load. Acceptable; it is what
  every form tool does.
- Concurrent collaborators: unchanged from today (last write wins on safe edits; one draft per
  survey enforced by the existing 409).

## Rollout

Kill switch `LIVE_SURVEY_EDITING` (default ON after review, like `EDITOR_AUTOSAVE`). Off ⇒ today's
read-only behaviour, which is the rollback.
