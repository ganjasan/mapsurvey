---
name: newsurvey
description: Interactively create a new survey definition that can be imported via /editor/import/. Use when the user wants to create a survey with questions and sections.
license: MIT
metadata:
  author: mapsurvey
  version: "1.0"
---

Create a new survey interactively and generate an importable ZIP archive.

**Output location**: `user_surveys/<survey_name>/`
- `survey.json` - Survey definition
- `<survey_name>.zip` - Ready for import via `/editor/` → Import Survey

## Steps

### 1. Ask for survey name

Use **AskUserQuestion** to get the survey name:
> "What should the survey be called? Use snake_case with Latin characters (e.g., `customer_feedback`, `field_inspection`)."

Validate: must be snake_case, Latin letters, numbers, underscores only. If invalid, ask again.

### 2. Create survey directory

```bash
mkdir -p user_surveys/<survey_name>
```

### 3. Interactive section loop

For each section:

**3.1. Ask section details** using AskUserQuestion:
- Section name (snake_case identifier)
- Section title (display text)
- Optional: subheading

**3.2. Interactive question loop** for this section:

For each question, ask:
- **Question type** - offer common types:
  - `text` - Multi-line text
  - `text_line` - Single line text
  - `number` - Numeric input
  - `choice` - Single selection
  - `multichoice` - Multiple selection
  - `point` - Map point (GIS)
  - `line` - Map line/route (GIS)
  - `polygon` - Map polygon (GIS)
  - `range` - Slider/range
  - `rating` - Star rating
  - `datetime` - Date and time picker
- **Question text** - The question to display
- **Required?** - Yes/No
- **For choice/multichoice/range/rating**: Ask for options (comma-separated list)
- **For point/line/polygon (geo questions)**:
  - Ask for **color** (HEX format, e.g., `#FF5733`, `#3388ff`) - used for marker/line/polygon color
  - **For point only**: Ask for **icon** (Font Awesome class, e.g., `fas fa-tree`, `fas fa-home`, `fas fa-parking`)

Generate unique question code: `Q_<SECTION>_<N>` (e.g., `Q_INTRO_1`, `Q_INTRO_2`) - max 50 chars

After each question, ask:
> "Add another question to this section?"

**3.3. After section questions complete**, ask:
> "Add another section to the survey?"

### 4. Generate survey.json

Create valid JSON in this exact format:

```json
{
  "version": "1.0",
  "exported_at": "<current ISO 8601 timestamp>",
  "mode": "structure",
  "survey": {
    "name": "<survey_name>",
    "organization": null,
    "redirect_url": "#",
    "sections": [
      {
        "name": "<section_name>",
        "title": "<section_title>",
        "subheading": "<subheading or null>",
        "code": "<CODE_8>",
        "is_head": true,
        "start_map_position": null,
        "start_map_zoom": 12,
        "next_section_name": "<next_section_name or null>",
        "prev_section_name": null,
        "questions": [
          {
            "code": "<question_code>",
            "order_number": 1,
            "name": "<question_text>",
            "subtext": null,
            "input_type": "<type>",
            "required": true,
            "color": "#000000",
            "icon_class": null,
            "image": null,
            "option_group_name": "<group_name or null>",
            "sub_questions": []
          }
        ]
      }
    ]
  },
  "option_groups": [
    {
      "name": "<group_name>",
      "choices": [
        {"name": "<choice_text>", "code": 1},
        {"name": "<choice_text>", "code": 2}
      ]
    }
  ]
}
```

**Important rules**:
- First section has `is_head: true`, others have `is_head: false`
- Section `code` must be max 8 characters (e.g., uppercase abbreviation like "INTRO", "SEC1")
- Section `name` must be max 45 characters, snake_case
- Section `start_map_zoom` must be integer (default 12), NEVER null
- Link sections: first section's `next_section_name` = second section's name, etc.
- For choice/multichoice/range/rating questions (REQUIRED):
  - MUST have `option_group_name` set - import will fail without it
  - Create OptionGroup named `<question_code>_opts` (keep short)
  - Set question's `option_group_name` to match
  - Each choice has `name` (display text) and `code` (integer, 1, 2, 3...)
- Question `order_number` starts at 1, increments per section
- For geo questions (point/line/polygon):
  - `color`: HEX color for marker/line/polygon (e.g., `#FF5733`), default `#000000`
  - `icon_class`: Font Awesome icon class for point markers (e.g., `fas fa-tree`), null for line/polygon

### 5. Create ZIP archive

```bash
cd user_surveys/<survey_name> && zip <survey_name>.zip survey.json
```

### 6. Show result

Output:
- Path to the ZIP file
- Import instructions:
  - **Web UI**: Go to `/editor/` → Click "Import Survey" → Upload the ZIP
  - **CLI**: `python manage.py import_survey user_surveys/<name>/<name>.zip`

## Example Session

```
User: /newsurvey

Claude: What should the survey be called? Use snake_case with Latin characters.
User: park_survey

Claude: Created directory user_surveys/park_survey/
         Let's add the first section.
         Section name (snake_case)?
User: intro

Claude: Section title (display text)?
User: Introduction

Claude: Now let's add questions to "intro" section.
         Question type?
User: text_line

Claude: Question text?
User: What is your name?

Claude: Required?
User: Yes

Claude: Added question Q_INTRO_1. Add another question to this section?
User: No

Claude: Add another section?
User: No

Claude: Survey created!
         - JSON: user_surveys/park_survey/survey.json
         - ZIP:  user_surveys/park_survey/park_survey.zip

         To import:
         - Web: /editor/ → Import Survey → upload park_survey.zip
         - CLI: python manage.py import_survey user_surveys/park_survey/park_survey.zip
```

## Guardrails

- Do NOT proceed without getting the survey name first
- Validate all names are snake_case Latin characters
- Survey name: max 45 characters
- Section name: max 45 characters
- Section code: max 8 characters (use uppercase abbreviation)
- Question code: max 50 characters
- `start_map_zoom`: always integer (default 12), NEVER null
- Generate unique question codes automatically
- OptionChoice needs `name` (text) and `code` (integer 1, 2, 3...)
- `color`: HEX format `#RRGGBB`, max 7 chars (e.g., `#FF5733`)
- `icon_class`: Font Awesome class, max 80 chars (e.g., `fas fa-tree`)
- Always create both survey.json AND the ZIP
- Include the current timestamp in exported_at
