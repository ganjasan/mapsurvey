## Context

`SurveyHeader.name` is a `CharField(max_length=45, validators=[validate_url_name])`
(`survey/models.py:320`). The validator name is a fossil: `url_name_validator` is
`RegexValidator(r'\w')` with the message "The name must contain at least one letter or
digit" (`survey/models.py:61`), so spaces, punctuation and non-Latin scripts all pass.
Routing uses `survey.uuid` throughout (`{% url 'survey' survey_slug=survey.uuid %}`), so a
rename changes no URL and invalidates no shared link.

The field is currently edited in exactly one place: `SurveyHeaderForm`
(`survey/editor_forms.py:112`), reachable through `editor_survey_settings` and its HTMX
twin `editor_survey_settings_panel` (`survey/editor_views.py:551` and `:570`). Neither
gates on survey status — an owner may already rename a published survey, and this change
does not alter that.

There is no inline-editing precedent in the editor: a grep for `contenteditable`,
`inline-edit` and `inlineEdit` across `survey/templates` and `survey/assets/js` returns
nothing. Whatever this change builds becomes the pattern the next inline edit copies.

## Goals / Non-Goals

Goals:
- A creator can rename a survey from any editor page without leaving it.
- Runtime and settings never disagree on what is a valid name.
- The 45-character limit is visible before it bites, not after.

Non-Goals:
- Changing the limit (see the truncation backlog item).
- A separate human-readable "title" alongside a machine "name". The field is already the
  human title; adding a second one would create a migration, a display-precedence rule and
  a translation question for no gain.

## Decisions

**One endpoint, one field.** A dedicated `editor_survey_rename` POST that accepts only
`name`, rather than reusing `editor_survey_settings_panel`. The settings panel POST binds
the full `SurveyHeaderForm` to `request.POST`; a partial post from the navbar would bind
`available_languages`, `basemaps` and `default_basemap` as absent and could rewrite them.
A one-field endpoint cannot damage anything but the name. It returns `{"ok": true, "name": …}`
or `{"ok": false, "errors": …}` with 400, matching the JSON contract
`editor_survey_settings_panel` already uses for AJAX.

**Validation runs through the model form, not by hand.** The endpoint binds a
single-field `ModelForm` on `SurveyHeader` so `max_length` and `validate_url_name` are
enforced by the same code as the settings page. A name of only spaces fails the `\w`
validator and is rejected with the existing message.

**The affordance is server-rendered, not JS-detected.** `_survey_title.html` renders an
editable control only when the viewer is an owner and the survey is not a draft copy. A
non-owner's page contains no input to re-enable from the
console; the endpoint's `@survey_permission_required('owner')` is the real gate, the markup
just does not lie about it.

**Escape restores, blur saves.** Blur-saves matches `EDITOR_AUTOSAVE`'s established
behaviour on question forms, so a creator who clicks away does not lose the edit. Escape
restores the pre-edit value and is the documented undo. There is no Cancel button: the
control must survive the mobile navbar grid, where row 1 is
`auto minmax(0,1fr) auto auto` and the title cell is the only flexible one
(`survey/assets/css/editor-mobile.css:132`).

**The title cell keeps its width.** In edit mode the input is sized to the cell, not to the
text, so entering edit mode does not reflow the navbar and push the version chip or the ⋯
overflow off the row. On mobile the span already ellipsises at one line; the input inherits
the same cell and scrolls horizontally instead of wrapping.

**The saved name is re-rendered from the response, not from the input.** The server's
returned value is what lands in the span, so any server-side normalisation is visible
immediately rather than at the next page load.

## Risks / Trade-offs

- **A rename on a published survey is instantly respondent-visible.** This is pre-existing
  (Survey settings does it today) but the header makes it one click away, so it will start
  happening. Mitigation: the change ships no confirmation dialog — a rename is trivially
  reversible and a modal on a title edit would be worse than the risk — but the endpoint is
  owner-only, which matches who may already do it.
- **Five templates converge on one partial.** If any of them relies on the current
  `Draft of …` branch or on its own markup, the consolidation is where a regression would
  land. Task 1 reads all five before touching any.
- **Blur-save plus a navbar click.** Clicking a navbar link while editing fires blur (save)
  and then navigation. The save request must not be cancelled by the navigation; it is sent
  with `keepalive` so a same-tick navigation does not drop it.
- **No feature flag.** The change ships unconditionally (owner decision, 2026-09-01: no new
  kill switches). Backing out is a revert, which the small blast radius — one partial, one
  endpoint, one script — makes cheap. The cost is paid up front in tests: the five headers,
  both permission outcomes and both length outcomes are covered before merge.

## Migration Plan

None — no schema change, and nothing to back-fill. Rollback is `git revert`.

## Open Questions

- Should a rename be recorded anywhere a collaborator can see it? There is no audit trail
  today (`feature-audit-trail.md` is unbuilt backlog); this change adds none.
