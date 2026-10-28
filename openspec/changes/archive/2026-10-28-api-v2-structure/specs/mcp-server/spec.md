## ADDED Requirements

### Requirement: Structure tools
The MCP server SHALL offer these read tools under `surveys:read`:

- `list_groups`
- `list_versions`
- `search_icons`

It SHALL offer these write tools under `surveys:write`:

- `create_group`, `update_group`, `delete_group`
- `duplicate_survey`, `duplicate_section`, `duplicate_question`
- `copy_question`, `copy_section`
- `move_question`
- `restore_version`

Each tool SHALL run over the service the REST routes call, with the same roles, locks and limits.
Argument models SHALL be the REST input schemas plus ids. `delete_group` with `with_questions: true`
SHALL require `confirm: true`. `restore_version` SHALL NOT require it, because it creates only
unpublished changes.

#### Scenario: Group questions from a chat
- **WHEN** an agent calls `create_group` with a title and three question ids
- **THEN** the result is the group with those `question_ids` and `get_survey` shows it in the section

#### Scenario: Find an icon before setting it
- **WHEN** an agent calls `search_icons` with `q: "bus stop"`
- **THEN** the result lists values such as `maki:bus` that `update_question` accepts as `icon_class`

#### Scenario: Deleting a group with its questions needs confirmation
- **WHEN** an agent calls `delete_group` with `with_questions: true` and no `confirm`
- **THEN** the result is `confirmation_required` and the group and its questions still exist
