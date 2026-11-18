## ADDED Requirements

### Requirement: Creator files hold no colour literals
The system's test suite SHALL fail when a creator template or stylesheet holds a colour in a CSS
declaration outside a `<script>` block. Files that render where the tokens stylesheet is not loaded
SHALL be listed as exceptions, each with its reason, and the list SHALL name only existing files.

#### Scenario: A literal returns to a creator file
- **WHEN** a colour literal is written into a style rule of the survey editor's base template
- **THEN** the test suite fails and names the file

#### Scenario: Colours handed to a map library
- **WHEN** a creator template passes a colour to Leaflet inside a `<script>` block
- **THEN** the test suite does not count it

#### Scenario: An email
- **WHEN** an email template writes its colours inline
- **THEN** the test suite accepts it, because the email is listed as rendering without the tokens
