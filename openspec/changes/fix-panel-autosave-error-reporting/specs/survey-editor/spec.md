## ADDED Requirements

### Requirement: Editor panel autosave error reporting
The system SHALL autosave every editor panel that has no explicit Save button — Survey settings, the Thanks page and Public results — through one shared implementation, and SHALL distinguish a failure the creator can act on from one they can only retry.

When a save is refused with HTTP 400 carrying an `errors` object, the panel SHALL name the
first failing field by the label the creator sees and quote its message, SHALL mark that
field as invalid, and SHALL NOT offer a retry, because re-posting the same value cannot
succeed. When a save fails for any other reason — a network error, a 403, a 5xx — the panel
SHALL say the save did not reach the server and SHALL make its status indicator a retry
control. A subsequent successful save SHALL clear every message and field mark the panel set.

An autosaver SHALL claim only the forms it was written for: the question-form autosaver SHALL
skip a form that carries no `hx-post`, so an editor panel is never saved twice, never posted to
a null URL, and never has another module's failure written into its status indicator.

Controls that live inside an autosaving form but save through their own endpoint — the
reference-layer card, the survey's auto-center switch, the Public results slug — SHALL NOT
trigger that form's autosave.

#### Scenario: A rejected field is named
- **WHEN** a creator types a malformed address into "Redirect URL" in the Survey settings panel and the server answers 400 with `{"errors": {"redirect_url": ["Enter a valid URL."]}}`
- **THEN** the status reads "Not saved — Redirect URL: Enter a valid URL.", the redirect_url input is marked invalid, and the status offers no retry

#### Scenario: A transport failure offers a retry
- **WHEN** a save fails because the request never reaches the server
- **THEN** the status says the change was not saved and names a retry, and clicking the status re-sends the save

#### Scenario: Retrying an invalid value is not offered
- **WHEN** the status is showing a validation failure and the creator clicks it
- **THEN** no request is sent

#### Scenario: A later success clears the report
- **WHEN** a validation failure has named a field and the creator corrects it, and the next save succeeds
- **THEN** the status returns to the saved state and the field is no longer marked invalid

#### Scenario: One implementation, not three copies
- **WHEN** the Survey settings, Thanks page and Public results panels render
- **THEN** each loads the shared panel autosave module and none of them defines an autosave status handler of its own

#### Scenario: One autosaver per form
- **WHEN** the Survey settings panel renders and a creator changes any field
- **THEN** only the panel autosaver posts, to the form's own action — the question autosaver does not claim the form, posts nothing, and writes nothing into the map position indicator that shares the form

#### Scenario: No redirect is a valid choice
- **WHEN** a creator clears "Redirect URL" in the Survey settings panel and the panel autosaves
- **THEN** the save succeeds and the survey stores the "#" sentinel that means "no redirect", rather than the panel refusing every later save with "This field is required"

#### Scenario: The auto-center switch does not fire the settings autosave
- **WHEN** a creator toggles "Auto-center on respondent's location" in the Survey settings panel
- **THEN** the map position endpoint receives the change and the settings form posts nothing, so a settings validation error cannot appear under the switch
