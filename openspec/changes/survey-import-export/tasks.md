## 1. Shared Serialization Module - Structure

- [x] 1.1 Create `survey/serialization.py` with export/import function signatures
- [x] 1.2 Implement `serialize_survey_to_dict(survey)` - convert survey to JSON-serializable dict
- [x] 1.3 Implement `serialize_option_groups(survey)` - collect and deduplicate OptionGroups
- [x] 1.4 Implement `serialize_sections(survey)` - sections with geo WKT and questions
- [x] 1.5 Implement `serialize_questions(section)` - questions with nested sub_questions
- [x] 1.6 Implement `collect_structure_images(survey)` - gather question images

## 2. Shared Serialization Module - Data

- [x] 2.1 Implement `serialize_sessions(survey)` - all sessions with answers
- [x] 2.2 Implement `serialize_answers(session)` - answers with nested sub_answers
- [x] 2.3 Implement geo field serialization (point/line/polygon to WKT)
- [x] 2.4 Implement choice serialization (ManyToMany to choice names)
- [x] 2.5 Implement `collect_upload_images(survey)` - user-uploaded answer images

## 3. Export ZIP Creation

- [x] 3.1 Implement `export_survey_to_zip(survey, output, mode)` - main export function
- [x] 3.2 Implement mode handling: structure, data, full
- [x] 3.3 Implement `validate_archive(zip_file)` - check structure, version, mode

## 4. Import Logic - Structure

- [x] 4.1 Implement Organization creation or reuse by name
- [x] 4.2 Implement OptionGroup/OptionChoice creation or reuse by name
- [x] 4.3 Implement SurveyHeader creation
- [x] 4.4 Implement SurveySection creation with WKT parsing
- [x] 4.5 Implement Question creation with hierarchy and unique code generation
- [x] 4.6 Build code remapping table (old_code → new_code) for collisions
- [x] 4.7 Implement structure image extraction to MEDIA_ROOT
- [x] 4.8 Resolve section next/prev links by name (warn if broken)

## 5. Import Logic - Data

- [x] 5.1 Implement `import_responses(archive, survey, code_remap)` - import with remapping
- [x] 5.2 Implement SurveySession creation
- [x] 5.3 Implement Answer creation with question lookup by remapped code
- [x] 5.4 Implement geo field parsing (WKT to point/line/polygon)
- [x] 5.5 Implement choice linking (names to OptionChoice objects)
- [x] 5.6 Implement hierarchical answer import (sub_answers)
- [x] 5.7 Implement upload image extraction to MEDIA_ROOT
- [x] 5.8 Handle missing question/choice references with warnings

## 6. Transaction and Validation

- [x] 6.1 Wrap structure import in atomic transaction
- [x] 6.2 Wrap data import in atomic transaction
- [x] 6.3 Validate data-only import requires existing survey

## 7. CLI Commands

- [x] 7.1 Create `survey/management/commands/export_survey.py`
- [x] 7.2 Add --mode flag (structure/data/full, default: structure)
- [x] 7.3 Add --output flag, default to stdout
- [x] 7.4 Add survey not found error handling
- [x] 7.5 Create `survey/management/commands/import_survey.py`
- [x] 7.6 Add stdin support with `-` argument
- [x] 7.7 Add file not found, survey exists, validation error handling

## 8. Web UI

- [x] 8.1 Add `export_survey` view with mode parameter
- [x] 8.2 Add `import_survey` view with file upload handling
- [x] 8.3 Add URL routes: `/editor/export/<name>/`, `/editor/import/`
- [x] 8.4 Update `editor.html` - add Export dropdown with mode options
- [x] 8.5 Update `editor.html` - add Import Survey button with file upload
- [x] 8.6 Add login_required decorator to both views
- [x] 8.7 Add success/error flash messages

## 9. Testing

- [ ] 9.1 Write test for structure serialization
- [ ] 9.2 Write test for data serialization (sessions, answers, geo, choices)
- [ ] 9.3 Write test for ZIP creation with all modes
- [ ] 9.4 Write test for CLI export/import commands
- [ ] 9.5 Write test for round-trip: export full → import → compare
- [ ] 9.6 Write test for data-only import to existing survey
- [ ] 9.7 Write test for error cases (missing survey, invalid archive, missing refs)
- [ ] 9.8 Write test for code remapping (collision → remap → responses use new code)
- [ ] 9.9 Write test for Web views (auth, modes, upload)
