## Why

Block 4 of epic #408 (#412). Parts of a survey's structure exist only in the editor, and their logic
lives in views, out of the API's reach:

- question groups (create, edit, delete);
- copying a question or section, and pasting from another survey;
- moving a question in or out of a pop-up;
- restoring a version.

An agent therefore cannot build a grouped questionnaire, reuse a survey, rearrange sections or roll
back a bad publish. It also has to guess icon names (`maki:bus`, `fas fa-tree`) that the editor's
picker finds by meaning.

Two things exist nowhere yet: **copying a whole survey** and **moving a question to another section**.
The owner decided (2026-10-25) that both arrive in this block on every surface — service, REST, MCP
and the editor.

Mapping the code also turned up a latent data-loss bug. Purging a survey from the trash deletes the
files of its cover, question images and layer assets (`survey/trash.py`). A cross-survey paste
already shares a question image's file with its source, so purging one survey breaks the other.
A whole-survey copy would spread the same fault to everything.

## What Changes

**Services (PR 1).** The editor and the API both call these.

- `survey/services/groups.py` — `create`, `update`, `delete` (only the group, or with its questions
  behind the answer-loss acknowledgement), plus translations.
  - Live rules: wording edits apply in place; create, delete and a rule change are structural.
  - Every write is audited.
  - `editor_group_views` calls the service; its responses do not change.
- `survey/services/structure.py`:
  - `duplicate_question`, `duplicate_section`, `paste_question`, `paste_section` — logic moved out of
    `editor_views`;
  - `move_question` — between the section and a pop-up, as `editor_question_move` does today, **and
    to another section of the same survey** (new);
  - `duplicate_survey` (new) — a new draft survey in the same workspace with its structure, groups,
    rules, translations and copies of its layers and their objects. No responses, versions, links or
    public results page are copied.
  - Every operation is audited.
- `cloning.copy_file()` — copied files get new storage keys (cover, question images, layer assets) on
  every cross-survey copy, including today's paste, so purging one survey never deletes another's
  files.
- `publishing.restore_version` gains an audit row (`version_restore`).

**REST (PR 1)**

- `GET|POST /sections/{id}/groups`; `GET|PATCH|DELETE /groups/{id}`.
  - Membership goes through the existing `PUT …/questions/order` with `{"g": id, "q": […]}`.
  - Question and survey output carry `group_id`; a section lists its groups.
- `POST /surveys/{uuid}/duplicate`, `POST /sections/{id}/duplicate`, `POST /questions/{id}/duplicate`.
- Cross-survey copy: `POST /sections/{id}/questions/copy` and `POST /surveys/{uuid}/sections/copy`
  take `{source_question_id | source_section_id}`.
- `POST /questions/{id}/move` with `{section_id?, parent_id?, position?, acknowledge_answer_loss?}`.
- `GET /surveys/{uuid}/versions`; `POST /surveys/{uuid}/versions/{n}/restore` (owner; creates
  unpublished changes).
- `GET /icons?q=&lang=&set=` — a search over `icon_catalog.json` with the picker's matching rules.
  Only drawable values are returned.

**MCP (PR 2)**

- Group tools: `list_groups`, `create_group`, `update_group`, `delete_group`.
- Copy and move tools: `duplicate_survey`, `duplicate_section`, `duplicate_question`, `copy_question`,
  `copy_section`, `move_question`.
- Version tools: `list_versions`, `restore_version`.
- `search_icons`.

**Editor (PR 1)**

- "Duplicate" in the survey's ⋯ menu on the dashboard. It opens the copy.
- "Move to section…" in the question row: a small menu of the survey's other sections. It goes
  through the structure gate on a live survey.

## Capabilities

### New Capabilities

### Modified Capabilities
- `rest-api-v1`: groups, copy/paste/duplicate, move, versions, icon search.
- `mcp-server`: structure tools.
- `question-groups`: group writes go through a service and are audited; a question moved to another
  section leaves its group.
- `survey-editor`: copy a whole survey; move a question to another section; cross-survey copies own
  their files.

## Impact

- New: `survey/services/groups.py`, `survey/services/structure.py`, `api/v1/structure.py`,
  `api/v1/icons.py`, `mcp/tools/structure.py`.
- Changed: `survey/cloning.py` (`clone_survey`, `copy_file`, layer copy); `editor_group_views.py`
  and the duplicate/paste/move views in `editor_views.py` (thin); `services/publishing.py` (audit);
  `api/v1/out.py` (`group_id`, groups, versions).
- Templates: `_survey_more_menu.html`, `question_list_item.html`, a small JS module.
- Model: `AuditLog.ACTION_CHOICES` plus a choices-only migration.
- Six catalogs gain new strings.
- References are regenerated.
