## Context

The entry form (change operator-entry) is already an editor: it loads a session's stored answers
into the respondent page's partials (`_build_section_context` with `session_id`), geo features
are restored into the same `editableLayers` group a freshly drawn feature joins, and their pop-up
carries the same Edit / Delete buttons. `save_section_answers` replaces the section's answers on
every POST. What is missing is navigation: a link in, a way back, and a record that a stored
sheet was changed.

## Goals / Non-Goals

**Goals:** one click from a paper response to the section holding its map answer; save one
section and land on the same response; an audit row for changes to a finished sheet.

**Non-Goals:** editing online sessions (they stay read-only); inline geometry editing inside the
Responses map modal; a diff of what changed; a scan pane beside the form (that is #511).

## Decisions

### D1. Return mode is a query parameter, not a session flag
`?return_to=response|map` rides the entry URL, `form_post_url` and every section URL the view
builds while it is set (Next, Back, the redirect to the chain start). Anything else in the
parameter is ignored. A flag in `request.session` would leak into the next sheet entered in
another tab. The value only chooses where the operator lands; it grants nothing.

### D2. "Save and return" is a third `nav_direction`
The button is a `type=submit` with `name="nav_direction" value="return"`, like Back. The view
saves through the same `save_section_answers` and only the redirect differs:
`editor_survey_analytics?session=<id>` (`&map=1` for `map`). It does not mark the session
completed: an operator fixing one point of an abandoned sheet has not finished it.

### D3. Edit links are built in the drawer view, gated there
`analytics_session_detail` asks `operator_entry_views.edit_links(request, survey, session)`,
which returns `None` unless the caller is `editor`+, the session is an operator session that is
not trashed, and the organisation `covers('operator_entry')` (the `sheet_gate` test). Otherwise
it returns the start URL (first visible section for the operator surface) and a function from
section name to URL. Rows get `edit_url`; geo features get `edit_url` in their properties (the
map modal reads the same `json_script` payload). The template never decides permission.

### D4. Responses opens `?session=<id>` itself
The v2 page calls `rv2OpenDrawer(id)` on load when `?session=` is present and the hash is not a
`#thread-` link (comments_drawer already handles that form). With `map=1` the full-size map opens
after the drawer partial is swapped in (`htmx:afterSwap` on `#rv2-drawer-body`, once). The id
goes through the same view and its family check, so a foreign id renders the drawer's 404.

### D5. An edit is a save on a completed operator session
`response_edit` is recorded when an entry POST hits a session whose `end_datetime` is already
set — the sheet was finished before, so this save changes it. Metadata: `session_id`,
`section` (the section code). A first pass through a sheet records nothing new. One row per
section save; no answer text.

## Risks / Trade-offs

- **#511 touches the same view and drawer** → keep additions in new helpers and context keys,
  not rewrites of existing lines.
- **Answer ids change on every save** (`save_section_answers` deletes and re-inserts) → the
  return lands on the response, not on a specific object id; the map re-opens fitted to all
  objects.
- **Migration for a choices change** → `0114`, `AlterField` only; no data touched.
