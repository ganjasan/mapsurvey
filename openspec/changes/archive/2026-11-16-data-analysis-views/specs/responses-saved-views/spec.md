## ADDED Requirements

### Requirement: A Responses filter is saved as a view of the survey's responses
The system SHALL let an editor of a survey save the Responses table's current filter — the
required-questions chip, the search text, the column filters, the sort and the version — under a
name, as a view of kind `responses` over the survey's responses dataset. Question columns SHALL be
stored by question code, never by row id.

#### Scenario: Saving the current filter
- **WHEN** an editor filters Responses to status "approved" and to "Bike" in the transport question, and saves it as "Approved cyclists"
- **THEN** the survey's responses dataset has a view "Approved cyclists" of kind `responses` whose columns name the status column and the transport question's code

#### Scenario: A viewer cannot save
- **WHEN** a member with the viewer role posts a view
- **THEN** the call is refused and nothing is saved

#### Scenario: A name is required
- **WHEN** an editor saves a view without a name
- **THEN** the view is refused

### Requirement: Opening a saved view applies the same filter
The system SHALL list a survey's saved views on the Responses table and SHALL, when one is opened,
show the rows the saved filter selects — also after unpublished changes were published since it was
saved. A column whose question no longer exists SHALL be ignored.

#### Scenario: Opening the view
- **WHEN** a member opens "Approved cyclists"
- **THEN** the table shows only approved responses whose transport answer is "Bike", and the table's state holds that filter for the next request

#### Scenario: After publishing changes
- **WHEN** unpublished changes are published, replacing the question rows, and the view is opened
- **THEN** the table shows the same responses as before

#### Scenario: The question was deleted
- **WHEN** the transport question is gone from every version and the view is opened
- **THEN** the table opens with the remaining filters and no error

#### Scenario: A view of another survey
- **WHEN** the table is asked for a view that belongs to another survey
- **THEN** the view is ignored

### Requirement: A saved view is managed like any view
The system SHALL show saved Responses views on the responses dataset's page with a link that opens
them in Responses, SHALL let an editor delete one, and SHALL refuse to delete a view a report uses.

#### Scenario: Listed on the dataset page
- **WHEN** an editor opens the responses dataset
- **THEN** "Approved cyclists" is listed with a link to Responses

#### Scenario: Deleting
- **WHEN** an editor deletes a saved view nothing uses
- **THEN** it is gone from the Responses list
