## Context

Attributes of a mapped object are modeled as sub-questions (`Question.parent_question_id`) whose answers attach to the geometry's answer (`Answer.parent_answer_id`). The editor Responses screen drops them everywhere:

- `SurveyAnalyticsService.get_geo_feature_collection` (`survey/analytics.py:304`) emits features with `properties = {question, type, session_id}` only, and the map layer (`analytics_geo_map.html`) binds no popup — feature clicks either drive `selectionManager` (pointer mode) or open the session modal (details mode).
- `format_session_answers` (`survey/analytics.py:675`) filters `parent_answer_id__isnull=True`, so even the session detail modal shows a geo answer as "point feature" with no attributes.

The two places that DO handle sub-answers are the ZIP export (`_export_survey_data` → `subAnswers()` + `_answer_cell`, `survey/views.py:1341-1349`) and the public results popup (`_collect_point_labels` + `_answer_display_value`, `survey/public_results.py:271-313`).

One session may contain several geometries for the same geo question, each with its own sub-answer set — attributes are per-object, not per-session.

## Goals / Non-Goals

**Goals:**
- A creator can see a mapped object's attributes by clicking its feature on the Responses map.
- The session detail modal lists each geo answer's sub-answers, grouped per object.
- One shared formatting path so map popup, modal, and (already-shipped) export agree on values.

**Non-Goals:**
- Charts/aggregations over sub-questions; CSV export of sub-answers; public results blocks.
- Inline editing of sub-answers (the `analytics_answer_edit` guard stays).
- Fixing the `get_answer_matrix` sub-answer overwrite bug (separate change).
- Filtering/selection by attribute values.

## Decisions

**D1. Sub-answers ride in GeoJSON `properties.attributes` as an ordered list of `{name, value}` pairs.**
A list (not a dict) preserves sub-question `order_number` and survives duplicate names. The existing keys (`question`, `type`, `session_id`) stay untouched so `selectionManager` styling and session lookups keep working. Alternative — a dict keyed by name, as in export properties — rejected: loses ordering and collides on duplicates.

**D2. Bulk-fetch, not `Answer.subAnswers()` per feature.**
`subAnswers()` issues one query per sub-question per answer — N+1 on a map with thousands of features. Instead: one query `Answer.objects.filter(parent_answer_id__in=<geo answer ids>).select_related('question')`, grouped in Python by `parent_answer_id_id`, ordered by `question.order_number`. Same approach `_collect_point_labels` already uses on the public page.

**D3. One display-value helper on the service, `_subanswer_display(answer)`.**
choice/multichoice/rating → `get_selected_choice_names()` joined; number/range → `numeric`; text/text_line/datetime → `text`; geo/image/html sub-types → skipped. Unanswered sub-questions are omitted (unlike export, which pads properties for a stable QGIS schema — a popup has no schema-stability need). Unlike the public page, free text IS shown: this is the creator viewing their own data behind auth, the privacy rules of `/r/<slug>/` do not apply.

**D4. Map popup opens on click in pointer mode, alongside selection; details mode is unchanged.**
Pointer-mode click already selects the session — a `L.popup` at the click point showing `question` + attribute rows adds information without changing selection semantics. Details mode keeps opening the modal, which now itself shows attributes (D5), so no popup is needed there. Features with an empty `attributes` list show the popup with only the question name — cheapest consistent behavior. Alternative — hover tooltips — rejected: unusable on touch and heavy with many overlapping features. Popup content is built from `feature.properties` with DOM-text assignment (no `innerHTML` with answer values) — sub-answer text is respondent input.

**D5. Modal: geo answer rows expand to one sub-list per object.**
`format_session_answers` keeps its top-level loop but, for geo answers, attaches `objects: [{index, attributes: [{name, value}]}]` to the answer row (and the same `attributes` into the mini-map feature properties). The template renders a small definition list under the geo row per object, numbered to match multiple geometries. Bulk-fetch as in D2 (a session has few answers; still one query for the whole session).

## Risks / Trade-offs

- [Map payload grows with attribute data on large surveys] → attributes are compact `{name, value}` strings; omitted when empty; no geometry duplication. If a survey with heavy text sub-answers ever hurts, a lazy per-feature endpoint is the escape hatch — not built now (YAGNI).
- [Popup vs. selection on the same click may feel noisy] → popup only carries content the creator asked to see; closing it does not clear selection. Ship behind the existing pointer-mode semantics, judge by use.
- [XSS via respondent sub-answer text in popup/modal] → popup rows are created via `textContent`; modal goes through Django template autoescape. No `|safe`, no string-built HTML.
- [Duplicate sub-question names render ambiguous rows] → accepted; names come from the creator's own structure, ordering (D1) keeps them distinguishable.

## Migration Plan

No migrations, no settings. Deploy is a normal merge; rollback is revert. The change is editor-only and additive — respondent flow, export, and public results untouched.

## Open Questions

None blocking.
