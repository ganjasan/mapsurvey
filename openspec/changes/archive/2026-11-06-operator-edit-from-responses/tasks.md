## 1. Audit action

- [x] 1.1 Add `('response_edit', 'Entered response edited')` to `AuditLog.ACTION_CHOICES`; migration `0114_auditlog_response_edit` (`AlterField` only) — check `origin/master` for a parallel `0114` first

## 2. Entry form: return mode and audit

- [x] 2.1 `operator_entry_views`: `RETURN_TARGETS = ('response', 'map')`, `_return_to(request)` reading GET (and POST for the form post), `_section_url(..., return_to=None)` appending the marker; Next/Back/chain-start redirects keep it
- [x] 2.2 `nav_direction == 'return'` with a valid marker: save, redirect to `editor_survey_analytics?session=<id>` (`&map=1` for `map`), HX-Redirect for HTMX; no `mark_completed`
- [x] 2.3 `response_edit` audit when the session's `end_datetime` was set before the save (`audit(request, 'response_edit', survey, session_id=…, section=section.code)`)
- [x] 2.4 Context `entry_return_to`; `entry_cancel_url` points at the response in return mode
- [x] 2.5 `survey_section_partial.html`: in `entry` + `entry_return_to`, a full-width *Save and return to Responses* submit (`nav_direction=return`) under Back/Next

## 3. Ways in from Responses

- [x] 3.1 `operator_entry_views.edit_links(request, survey, session)` → `None` or `{'start': url, 'section': fn(name, return_to)}`, gated by role, `is_operator_entry`, not trashed, `covers('operator_entry')`
- [x] 3.2 `format_session_answers` rows carry `section_code_name` (the section's `name`); `analytics_session_detail` sets `row.edit_url` and `feature.properties.edit_url` from `edit_links`, passes `edit_start_url`
- [x] 3.3 Drawer template: *Edit response* button in the header actions; section name under each question becomes a link when `row.edit_url`
- [x] 3.4 Map modal: header *Edit on the map* link (target object's `edit_url`, else first feature's), pop-up link per feature built through the DOM; hidden when no feature has `edit_url`
- [x] 3.5 v2 page: on load, `?session=<id>` without `#thread-` → `rv2OpenDrawer(id)`; `map=1` → open the full map after the drawer swap

## 4. Strings

- [x] 4.1 `Edit response`, `Edit on the map`, `Save and return to Responses`, `Edit this section` in every maintained catalog (en, ru, de, fr, es, pt, pl, id, nl, it, et, fi), compile `.mo`

## 5. Tests (`survey/tests/test_operator_entry.py`, `survey/tests/test_responses_detail_drawer.py`)

- [x] 5.1 Drawer links: paper session shows Edit + section links + feature `edit_url`; online, viewer, lapsed, trashed show none
- [x] 5.2 Return mode: button only with a valid marker; Next keeps the marker; *Save and return* redirects to `?session=<id>[&map=1]`, does not complete an abandoned sheet; Stop points at the response
- [x] 5.3 Geometry: moved point, reshaped line, deleted polygon, changed sub-answer on stored features
- [x] 5.4 Unchanged resave from the rendered form keeps every answer value
- [x] 5.5 Audit: edit of a completed sheet writes `response_edit`; a first entry writes none
- [x] 5.6 Drawer page carries the `?session=` opener
- [x] 5.7 Run `survey.tests.test_operator_entry survey.tests.test_responses_detail_drawer survey.tests.test_ui_internationalization survey.tests.test_test_suite`

## 6. Verify

- [x] 6.1 Local stand: paper response → Edit on the map → move a point → Save and return → drawer + map show the new position (screenshots)
- [x] 6.2 Found on the stand: the full-size map opened without an object (`sessionGeoOpenMap(null)`, now every map return) fitted a one-point response to zoom 23, past the tiles — `maxZoom: 17` on that branch too; the modal's Edit button sits beside the close button (`close ml-0`)
