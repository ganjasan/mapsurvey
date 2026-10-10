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
inline confirmation) and how it is presented. Every structural control on a live survey carries
`data-gate="<action>"` (and the section code) instead of its request; one capturing click
listener opens the gate modal, whose form posts `then` + `section_code` to `editor_create_draft`.
The draft opens on the section with the same `code` (codes are preserved by the clone).
`add_question` and `add_section` are replayed by clicking the same control once on the draft
page; the other actions (delete, duplicate, reorder, type, visibility) are not replayed — the
creator lands on the same section, where the control now works, under a toast that says they are
editing unpublished changes. Replaying a delete without a second look would be worse than one
more click.

Server side nothing structural becomes possible on a live survey: the structural endpoints keep
`_check_structural_edit_allowed` (403); the content endpoints (`editor_section_detail` POST,
`editor_question_edit`, `editor_question_share`, `editor_section_map_picker` POST) go through
`_check_content_edit_allowed` and, for the fields a content form also carries, through
`structural_question_changes` / `structural_section_changes`. `QuestionForm` and
`SurveySectionForm` take `lock_structure=True`, which disables `input_type`, `layer` and the
section `code` so a posted value is ignored rather than refused.

### D4. One editing surface per survey

`editor_survey_detail` on a canonical survey that has a draft copy redirects to the draft unless
`?live=1`. The draft page carries the live survey's name (no "Draft of" prefix; the `[draft]`
stored name stays for admin/back-compat but is never rendered) plus an "Unpublished changes" pill
and a "View live version" link. Results/Share/Public-results tabs on the draft keep pointing at the
canonical (already the case via `canonical_of`).

### D4b. Who may start them

Editors as well as owners (owner decision 2026-10-10): an editor may add a question to a draft
survey, so refusing them the same edit on a live survey would bring the wall back for every team.
Publishing and discarding stay owner-only — that is the moment respondents' survey changes — and an
editor on the changes sees "The survey owner publishes these changes" where the button would be.

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

Kill switch `LIVE_SURVEY_EDITING` (default ON, like `EDITOR_AUTOSAVE`). Off ⇒ the pre-change
read-only behaviour and vocabulary, which is the rollback.

## Translations

The new strings are English only for now. The creator catalogs already lag the templates by about a
thousand msgids (makemessages over the current tree), so adding these few would not make any
language complete; the catalog refresh is its own piece of work.
