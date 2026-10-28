## Context

Two code paths deep-copy survey structure: `cloning.clone_section` (editor duplicate / paste,
regenerates codes) and `versioning.clone_survey_for_draft` (draft copy, keeps codes). Both list
`SurveySection` fields by hand, and the second list was last touched before `layout` (0058),
`next_label` (0059), `visibility_rule` (0062) and `hidden_layers` existed. `clone_question` lists
`Question` fields by hand too, and decides whether a rule survives by `same_survey`.

## Decisions

### Field lists come from the model, not from the author

`cloning.plain_field_values(instance, exclude)` returns `{attname: value}` for every concrete,
non-relational, non-primary-key field of the instance. Section copies pass the fields that need a
decision (`is_head`, `name`, `title`, `code` stay explicit where the caller changes them; the
linked list is resolved by the caller) and spread the rest. The same helper feeds `clone_question`
(code, name, parent, section, layer and visibility rule stay explicit). A new plain field is copied
on day one; a field that must NOT be copied is added to the exclusion set, which is the explicit
exception rather than the default.

Alternative considered: keep the hand-written lists and add a test. Rejected — the test catches the
omission but the fix is still a list edit in two files; introspection removes the class of bug.

### A rule survives when the controller code survives

`clone_question` keeps `visibility_rule` when the copy stays in the same survey OR codes are not
regenerated (`regenerate_code=False` is the versioning path: the whole survey is copied with its
codes, so the controller exists in the target). Cross-survey paste still drops it.
`clone_section` keeps a section rule only in-survey, as before (its controller lives in an EARLIER
section that does not travel on a paste); the draft path copies every section, so the rule is
kept there.

### `hidden_layers` ids stay valid

Layers belong to the canonical survey and are borrowed by the draft (`layers_for`), so the ids a
section hides are the same rows in the draft and after publish. Copying the list verbatim is
correct; a cross-survey paste (`clone_section`) keeps it as before — stale ids are ignored by the
reader, as the field's help text says.

### Repair is a report, not a migration

`python manage.py report_draft_field_loss` walks every canonical survey with archived versions,
and for each lineage (question codes / section codes are stable) prints where the newest archived
version has a rule, a non-default layout, a button label or hidden layers that the current
canonical row lacks. Read-only; the owner restores by hand (or by restoring the version as a new
draft, which now keeps the fields).

## Risks

`clone_question` switching to introspection changes nothing for the fields it already copied —
the guard test pins that. `CloningPrimitiveTest`, `EditorSectionDuplicateTest` and
`VersioningRegressionTest` cover the editor paths.
