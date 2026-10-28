## ADDED Requirements

### Requirement: Group writes go through one service and are audited
Creating, editing and deleting a group SHALL go through `survey/services/groups.py` on every
surface: the editor, REST and MCP. Each write SHALL leave an audit row (`group_create`,
`group_update`, `group_delete`). The editor's group endpoints SHALL keep their responses, statuses
and messages.

#### Scenario: Editor group edit is audited
- **WHEN** a creator renames a group in the editor
- **THEN** an audit row `group_update` names the group and the editor's response is unchanged

### Requirement: A question moved to another section leaves its group
Moving a question to another section SHALL clear its group. A group left without members SHALL stay
as an empty group.

#### Scenario: Last member moves away
- **WHEN** the only member of a group is moved to another section
- **THEN** the question has no group and the empty group remains in the old section
