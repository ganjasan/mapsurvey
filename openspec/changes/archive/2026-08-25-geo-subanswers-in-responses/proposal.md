## Why

Creators are told to model attributes of a mapped object as sub-questions of the geo question (the sub-question name becomes the GeoJSON property), yet the editor's Responses screen never shows those sub-answers: map features carry only `{question, type, session_id}` and the session detail modal filters answers to `parent_answer_id__isnull=True`. Today the only way for a creator to see the attributes their respondents entered is to download the ZIP export and open the GeoJSON in QGIS — the product collects the data but cannot display it.

## What Changes

- Responses map: clicking a geo feature shows a popup with that object's sub-answers (attribute name → value), in addition to the existing selection / session-modal behavior. Features with no sub-answers keep current behavior.
- Session detail modal: each geo answer lists the sub-answers attached to it (per object, since one session can contain several geometries each with its own attribute set).
- Geo feature payloads (`get_geo_feature_collection`, `format_session_answers`) carry sub-answer data in GeoJSON `properties`, mirroring what the ZIP export already writes.
- Out of scope: charts/aggregations over sub-questions, CSV export of sub-answers, public results page blocks, inline editing of sub-answers, the `get_answer_matrix` overwrite bug (noted for a follow-up change).

## Capabilities

### New Capabilities
- `responses-geo-subanswers`: visibility of geo sub-question answers (mapped-object attributes) in the editor Responses screen — map feature popup and session detail modal.

### Modified Capabilities

(none — no existing spec covers the Responses analytics screen; export and public-results behavior is unchanged)

## Impact

- `survey/analytics.py` — `get_geo_feature_collection` (`:304-338`) and `format_session_answers` (`:675-720`) gain sub-answer properties; must reuse `Answer.subAnswers()` / bulk-fetch to avoid N+1 on large surveys.
- `survey/templates/editor/partials/analytics_geo_map.html` — popup rendering on feature click, coexisting with `window.selectionManager` selection and `openSessionDetailModal`.
- `survey/templates/editor/partials/analytics_session_detail.html` — sub-answer list under each geo answer.
- Value formatting: reuse the display logic already proven in ZIP export (`_answer_cell`, `survey/views.py:1345`) and public-results popups (`_answer_display_value`, `survey/public_results.py:303`) so the three surfaces agree.
- No model or migration changes; no API surface outside the editor; performance risk limited to the extra sub-answer query on map/table payloads.
