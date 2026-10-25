## 1. Service and safety (PR 1)

- [x] 1.1 `layers.clean_object_link`; applied in the object editor PATCH, GeoJSON mapping, CSV import, ZIP manifest (imports drop + count); `object_card_payload` and `layer_objects_block.html` render http(s) only
- [x] 1.2 `survey/services/layers.py`: create (bytes/features/empty), update, delete (`LayerInUse`), reorder, object create/update/delete, mark status; lock, caps, rebuild, audit
- [x] 1.3 Editor views (`editor_survey_layer_*`, `layer_object_views` object endpoints, `analytics_object_status`) call the service; responses and messages unchanged
- [x] 1.4 `_resolve_layer_choice` respects `MAX_LAYERS_PER_SURVEY`; `forms_bridge` maps `layer_from_answers`
- [x] 1.5 `AuditLog.ACTION_CHOICES` + migration `0103` (choices only)

## 2. REST (PR 1)

- [x] 2.1 `api/v1/layers.py`: create (JSON / multipart), patch, delete, order; objects list/get/create/patch/delete; mark status; schemas; `out.layer` extended
- [x] 2.2 Question schemas: `layer_from_answers`
- [x] 2.3 Tests per scenario (incl. geometry never loaded on rename, editor layer tests unchanged, XSS link refused/inert/dropped); `scripts/build_api_reference.py`
- [x] 2.4 `./run_tests.sh api survey`

## 3. MCP (PR 2)

- [ ] 3.1 `mcp/tools/layers.py`: ten tools; confirm on deletes
- [ ] 3.2 Tests; `scripts/build_mcp_reference.py`; help (what to ask about map layers); MCP changelog entry one sentence at most
- [ ] 3.3 `./run_tests.sh api mcp survey`; `npm run build` in `help/`
