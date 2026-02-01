## Context

Survey definitions are created through Django admin and consist of multiple related models: SurveyHeader → SurveySection → Question → OptionGroup → OptionChoice. The relationships include:
- Foreign keys (survey_section → survey_header, question → option_group)
- Self-referential links (parent_question_id, next_section/prev_section)
- ManyToMany (Answer.choice)
- ImageField on Question model

Currently there's no way to backup or transfer survey structures between environments. The `/editor/` dashboard shows surveys with Download (responses) action but no structure export. Survey administrators need self-service export/import without requiring SSH access.

## Goals / Non-Goals

**Goals:**
- Export complete survey definition including media files to downloadable ZIP
- Import survey from ZIP, creating all related objects with correct relationships
- Web UI in `/editor/` dashboard for survey administrators
- CLI commands for automation and scripting
- Handle ID remapping during import (source IDs ≠ target IDs)
- Validate archive structure before import to fail fast

**Non-Goals:**
- Exporting/importing survey responses (Answer, SurveySession) - structure backup only
- Updating existing surveys - users should delete and reimport manually if needed
- Merging surveys or partial imports
- Cross-organization survey sharing (import creates in current user context)

## Decisions

### 1. ZIP as export format
**Choice**: ZIP archive containing `survey.json` + `images/` folder
**Alternatives considered**:
- JSON only: Can't include media files, users need SSH for manual copy
- Base64 in JSON: Works but bloats file size significantly
- Tar.gz: Less universal tooling support

**Rationale**: ZIP is universally supported, allows streaming, and separates data from media cleanly.

### 2. Export modes
**Choice**: Three modes via `?mode=` parameter
- `structure` (default): Survey definition + question images
- `data`: Responses only (sessions, answers, geo data)
- `full`: Complete backup (structure + data)

**Rationale**: Different use cases require different exports. Migration needs structure only; analysis needs data only; backup needs everything.

### 3. Archive structure
```
survey_<name>.zip
├── survey.json          # Structure (modes: structure, full)
├── responses.json       # Data (modes: data, full)
└── images/
    ├── structure/       # Question images
    └── uploads/         # User-uploaded images (Answer)
```

**survey.json structure**:
```json
{
  "version": "1.0",
  "exported_at": "ISO timestamp",
  "mode": "structure|data|full",
  "survey": {
    "name": "...",
    "organization": "org_name or null",
    "sections": [...]
  },
  "option_groups": [...]
}
```

**responses.json structure**:
```json
{
  "sessions": [
    {
      "id": 1,
      "start_datetime": "ISO",
      "end_datetime": "ISO or null",
      "answers": [
        {
          "question_code": "Q_123",
          "numeric": 5,
          "text": "...",
          "point": "POINT(30 60)",
          "choices": ["choice_name_1", "choice_name_2"],
          "sub_answers": [...]
        }
      ]
    }
  ]
}
```
**Rationale**: Use question codes and choice names for references instead of IDs. Geo fields serialized as WKT.

### 4. Shared serialization module
**Choice**: `survey/serialization.py` with reusable functions for both CLI and Web
**Rationale**: DRY principle. CLI commands and Web views call same logic.

```python
# survey/serialization.py
def export_survey_to_zip(survey: SurveyHeader, output: IO[bytes]) -> None
def import_survey_from_zip(input: IO[bytes], user: User) -> SurveyHeader
```

### 5. Import strategy: Create-only
**Choice**: Import always creates new records, refuses if survey name exists
**Alternatives considered**:
- Update existing: Risk of data corruption, complex merge logic
- Force overwrite with --force flag: Dangerous for production

**Rationale**: Safer default. Users can delete existing survey manually if needed.

### 6. Section ordering via names
**Choice**: Store `next_section_name` instead of FK IDs
**Rationale**: Section names are unique within survey. After all sections are created, a second pass resolves next/prev links by name lookup.

### 7. Web UI placement
**Choice**: Add "Export" link per survey row + "Import Survey" button in `/editor/`
**Rationale**: Matches existing UI pattern (Download link per row). Import is global action.

## Risks / Trade-offs

**[Risk] Circular references in section links** → Validate section chain integrity before export; warn on import if chain is broken

**[Risk] Missing OptionGroup referenced by Question** → Export includes all referenced OptionGroups; import creates them before Questions

**[Risk] Large surveys with many images** → ZIP streaming handles large files; no memory issues for typical surveys

**[Risk] Filename collisions in images/** → Prefix with question code: `Q_123_original.jpg`

**[Risk] Question code collisions break response import** → Build code remapping table during structure import. When importing responses, translate `question_code` references using this table. Same applies to parent_question references within the archive.

**[Trade-off] Organization handling** → Export org name only. Import creates org if missing or uses existing by name.

**[Trade-off] Permission model** → Any authenticated user can export surveys visible to them. Import creates survey owned by importing user.
