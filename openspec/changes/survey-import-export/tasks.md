## 1. Shared Serialization Module - Structure

- [ ] 1.1 Create `survey/serialization.py` with export/import function signatures
- [ ] 1.2 Implement `serialize_survey_to_dict(survey)` - convert survey to JSON-serializable dict
- [ ] 1.3 Implement `serialize_option_groups(survey)` - collect and deduplicate OptionGroups
- [ ] 1.4 Implement `serialize_sections(survey)` - sections with geo WKT and questions
- [ ] 1.5 Implement `serialize_questions(section)` - questions with nested sub_questions
- [ ] 1.6 Implement `collect_structure_images(survey)` - gather question images

## 2. Shared Serialization Module - Data

- [ ] 2.1 Implement `serialize_sessions(survey)` - all sessions with answers
- [ ] 2.2 Implement `serialize_answers(session)` - answers with nested sub_answers
- [ ] 2.3 Implement geo field serialization (point/line/polygon to WKT)
- [ ] 2.4 Implement choice serialization (ManyToMany to choice names)
- [ ] 2.5 Implement `collect_upload_images(survey)` - user-uploaded answer images

## 3. Export ZIP Creation

- [ ] 3.1 Implement `export_survey_to_zip(survey, output, mode)` - main export function
- [ ] 3.2 Implement mode handling: structure, data, full
- [ ] 3.3 Implement `validate_archive(zip_file)` - check structure, version, mode

## 4. Import Logic - Structure

- [ ] 4.1 Implement Organization creation or reuse by name
- [ ] 4.2 Implement OptionGroup/OptionChoice creation or reuse by name
- [ ] 4.3 Implement SurveyHeader creation
- [ ] 4.4 Implement SurveySection creation with WKT parsing
- [ ] 4.5 Implement Question creation with hierarchy and unique code generation
- [ ] 4.6 Build code remapping table (old_code → new_code) for collisions
- [ ] 4.7 Implement structure image extraction to MEDIA_ROOT
- [ ] 4.8 Resolve section next/prev links by name (warn if broken)

## 5. Import Logic - Data

- [ ] 5.1 Implement `import_responses(archive, survey, code_remap)` - import with remapping
- [ ] 5.2 Implement SurveySession creation
- [ ] 5.3 Implement Answer creation with question lookup by remapped code
- [ ] 5.4 Implement geo field parsing (WKT to point/line/polygon)
- [ ] 5.5 Implement choice linking (names to OptionChoice objects)
- [ ] 5.6 Implement hierarchical answer import (sub_answers)
- [ ] 5.7 Implement upload image extraction to MEDIA_ROOT
- [ ] 5.8 Handle missing question/choice references with warnings

## 6. Transaction and Validation

- [ ] 6.1 Wrap structure import in atomic transaction
- [ ] 6.2 Wrap data import in atomic transaction
- [ ] 6.3 Validate data-only import requires existing survey

## 7. CLI Commands

- [ ] 7.1 Create `survey/management/commands/export_survey.py`
- [ ] 7.2 Add --mode flag (structure/data/full, default: structure)
- [ ] 7.3 Add --output flag, default to stdout
- [ ] 7.4 Add survey not found error handling
- [ ] 7.5 Create `survey/management/commands/import_survey.py`
- [ ] 7.6 Add stdin support with `-` argument
- [ ] 7.7 Add file not found, survey exists, validation error handling

## 8. Web UI

- [ ] 8.1 Add `export_survey` view with mode parameter
- [ ] 8.2 Add `import_survey` view with file upload handling
- [ ] 8.3 Add URL routes: `/editor/export/<name>/`, `/editor/import/`
- [ ] 8.4 Update `editor.html` - add Export dropdown with mode options
- [ ] 8.5 Update `editor.html` - add Import Survey button with file upload
- [ ] 8.6 Add login_required decorator to both views
- [ ] 8.7 Add success/error flash messages

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
