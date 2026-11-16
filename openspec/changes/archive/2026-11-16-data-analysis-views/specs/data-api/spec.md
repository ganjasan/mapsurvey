## ADDED Requirements

### Requirement: Analysis views are created and read through REST and MCP
The system SHALL let a client create a view of any kind its dataset allows by naming `kind` and the
kind's `config`, SHALL return a computed view's result from `GET /datasets/{id}/views/{view}/data`
and from the MCP tool `get_dataset_view_data`, and SHALL refuse `data` for a view that is a saved
filter with a message naming where it is read.

#### Scenario: Creating a cross-tab over REST
- **WHEN** a client posts a view with kind `crosstab` and config naming two choice questions on a responses dataset
- **THEN** the view is created and its data holds the table with masked cells

#### Scenario: A kind the dataset does not allow
- **WHEN** a client posts kind `engagement` on a layer dataset
- **THEN** the call is refused with 422 naming `kind`

#### Scenario: An agent reads engagement
- **WHEN** an agent creates an engagement view with `create_dataset_view` and calls `get_dataset_view_data`
- **THEN** the result holds the opened, answered and finished steps

#### Scenario: Data of an objects view
- **WHEN** a client reads `data` of an objects view
- **THEN** the call is refused with 409 naming the features endpoint
