## Context

`SurveyHeader.name` has `unique=True` at the database level. All URLs — both public (`/surveys/<name>/`) and editor (`/editor/surveys/<name>/`) — use this name as the lookup key. There is no UUID field on SurveyHeader. There is no `owner`/`user` FK either — surveys are only optionally linked to an Organization.

The name field serves dual duty: human-readable identifier AND unique URL slug. This is the root cause — removing global uniqueness requires a new unambiguous identifier for URLs.

~25 view functions do `get_object_or_404(SurveyHeader, name=survey_name)` or `SurveyHeader.objects.get(name=survey_name)`. ~40 template references build URLs with `survey.name`.

## Goals / Non-Goals

**Goals:**
- Allow multiple users to create surveys with the same name (e.g., "DEMO", "TEST")
- Introduce UUID as the stable, unique identifier for all URL routing
- Keep survey names as human-readable labels (displayed in UI, used in exports)
- Maintain backward compatibility for existing surveys via name-based fallback on public URLs

**Non-Goals:**
- Adding an `owner`/`user` FK to SurveyHeader (separate concern, not needed for this change)
- Per-user name uniqueness validation (no user FK exists; can be added later)
- Changing the `name` field format or validation rules

## Decisions

### D1: Use UUID v4 for survey identification

**Choice**: Add `SurveyHeader.uuid` as `UUIDField(default=uuid.uuid4, unique=True, editable=False)`.

**Why**: UUIDs are globally unique without coordination, fit Django's `<uuid:>` URL converter natively, and are standard for multi-tenant systems. Alternatives considered:
- Auto-increment ID: exposes record count, sequential guessing
- Hashid/short-id: extra dependency, encoding layer
- Slug with owner prefix: no owner FK exists

### D2: Editor URLs use UUID exclusively

**Choice**: All `/editor/` routes change from `<str:survey_name>` to `<uuid:survey_uuid>`.

**Why**: Editor is authenticated, no SEO concerns, UUID guarantees uniqueness. The editor has ~15 URL patterns — all will use `survey_uuid`. Lookup becomes `get_object_or_404(SurveyHeader, uuid=survey_uuid)`.

### D3: Public URLs use `<str:survey_slug>` with dual lookup

**Choice**: Public routes (`/surveys/<survey_slug>/...`) accept either UUID or name. Lookup order:
1. Try UUID parse → `SurveyHeader.objects.get(uuid=parsed_uuid)`
2. Fall back to name → `SurveyHeader.objects.get(name=survey_slug)`
3. If name matches multiple surveys → return 404 (ambiguous)

**Why**: Preserves existing bookmarks/links. Once names collide, UUID URLs become the only working path. A helper function `resolve_survey(survey_slug)` centralizes this logic.

**Alternative considered**: UUID-only public URLs — simpler but breaks all existing links.

### D4: Export/delete URLs use UUID

**Choice**: `/editor/export/<uuid:survey_uuid>/` and `/editor/delete/<uuid:survey_uuid>/`.

**Why**: These are authenticated editor actions — same reasoning as D2.

### D5: Remove name uniqueness check from import

**Choice**: `create_survey_header()` in serialization.py drops the `if SurveyHeader.objects.filter(name=name).exists()` check. Import always creates a new survey (with a new UUID).

**Why**: With non-unique names, the check is meaningless. If a user imports a survey with the same name as an existing one, that's fine — they're different surveys with different UUIDs.

### D6: Data-only import uses name with ambiguity check

**Choice**: Data-only import (`responses.json` without `survey.json`) still matches by `survey_name`. If multiple surveys share the name, raise an error suggesting UUID-based matching in the future.

**Why**: Data-only import is a less common flow. Full UUID-based data import is a future enhancement (would require `survey_uuid` in responses.json).

### D7: Three-step migration

**Choice**:
1. Migration 0009: Add `uuid` field as nullable UUIDField
2. Migration 0010: Data migration — populate UUID for all existing rows
3. Migration 0011: Make `uuid` non-null + unique, remove `unique=True` from `name`

**Why**: Safe for existing data. Can't add non-null unique field in one step with existing rows.

### D8: Templates use `survey.uuid` for URL building

**Choice**: All template URL references change from `survey.name` to `survey.uuid` for editor routes. Public-facing links (landing page, survey list) can use either — UUID preferred for unambiguous linking.

**Why**: Direct consequence of D2/D3.

## Risks / Trade-offs

- **[Existing bookmarks break for editor URLs]** → Editor URLs are only used by authenticated users; impact is low. Redirect middleware is not worth the complexity.
- **[Public name-based URLs become ambiguous]** → When two surveys share a name, name-based URLs return 404. This is by design — UUID URLs always work. Mitigation: landing page and survey list templates will link using UUID.
- **[Large diff across views/templates]** → ~25 view functions and ~40 template references need updating. Mitigation: mechanical find-and-replace; `resolve_survey()` helper reduces view changes.
- **[Management command `export_survey` uses name]** → Update to accept either name or UUID. If name is ambiguous, print error listing matching UUIDs.

## Open Questions

None — the design is straightforward given the constraint that no user FK exists.
