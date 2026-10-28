## ADDED Requirements

### Requirement: External scripts are loaded so their errors are readable

Every `<script>` element in the templates that loads JavaScript from an external origin SHALL carry
`crossorigin="anonymous"`, so that an exception thrown by that script reaches error tracking with its
message, source and stack rather than being sanitised to `Script error.`

The attribute SHALL be `anonymous` rather than `use-credentials`: no credentials are sent to
third-party hosts, and the hosts we load from answer with a wildcard origin, which a credentialed
request would reject outright.

#### Scenario: Every external script tag carries the attribute
- **WHEN** the template tree is scanned for script elements with an external `src`
- **THEN** each one carries `crossorigin="anonymous"`

#### Scenario: A new external script without the attribute fails the guard
- **GIVEN** a template gains a new `<script>` pointing at an external host
- **WHEN** the guard runs
- **THEN** it fails, naming the file and the URL

#### Scenario: Loading is unaffected
- **WHEN** a page carrying these scripts is loaded in a browser
- **THEN** every external script still loads and executes as before
