# data-api Specification

## Purpose
The Data module in REST API v1 and MCP: datasets, features (layers only, without private fields), views, uploads, versions and survey links under the editor's rights and refusals, every write through `data.services` with an Actor. Implementation: `data/services.py`, `api/v1/datasets.py`, `mcp/tools/data.py`; tests `survey/tests/test_data_api.py`.
## Requirements
### Requirement: An agent works with Data through MCP alone
The system SHALL let an MCP client upload a file as a workspace dataset, follow its job, describe it,
label its fields, make it public and link it into a survey with the Data tools, under the same rights,
plan gate and refusals as the editor.

#### Scenario: Upload, describe, link
- **WHEN** an agent uploads a tree register CSV, sets its licence, labels a field, makes it public and links it into a survey
- **THEN** the survey's layer GeoJSON carries the trees with the labelled field and no private column

#### Scenario: A private dataset cannot be linked
- **WHEN** an agent links a dataset that is still private into a survey
- **THEN** the call is refused with the message to make it public first

### Requirement: The REST API reads and writes datasets under the editor's rules
The system SHALL list and read datasets, their features, views and versions, and SHALL edit details,
fields and views, upload datasets and versions, and link datasets into surveys through REST API v1.
Private fields SHALL never be returned and collected answers SHALL leave only as a grid view.

#### Scenario: Features without private fields
- **WHEN** a client reads a layer dataset's features
- **THEN** no feature carries a private field

#### Scenario: Collected answers stay aggregated
- **WHEN** a client reads an answers dataset's features
- **THEN** the call is refused with 409, and its grid view's features carry only cells and counts

#### Scenario: A licence outside the list
- **WHEN** a client patches a dataset's licence to `gpl-3.0`
- **THEN** the call is refused with 422 naming the field

#### Scenario: A version over REST
- **WHEN** a client uploads a new version and applies it with a note
- **THEN** the dataset lists version 2 with the note

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

