## MODIFIED Requirements

### Requirement: Age and terms confirmation on sign-up

The registration form SHALL include a required checkbox field `accept_terms` labelled "I am 16 or older and accept the Terms of use", where "Terms of use" links to `/terms/`. A submission without it SHALL fail form validation with HTTP 200 and a field error, and SHALL NOT create a user. The honeypot check SHALL still run before form validation, so a bot that fills the honeypot and omits `accept_terms` SHALL still receive the fake-success redirect. Existing accounts SHALL NOT be asked to confirm. The checkbox SHALL render at its natural size to the left of its label text, on the same line.

#### Scenario: Missing confirmation is rejected

- **WHEN** a registration with valid data, empty honeypot and valid Turnstile token is submitted without `accept_terms`
- **THEN** the response SHALL be HTTP 200 with an error on `accept_terms`
- **AND** no `User` SHALL be created

#### Scenario: Honeypot still wins

- **WHEN** a registration fills the honeypot field and omits `accept_terms`
- **THEN** the response SHALL be the fake-success redirect and no `User` SHALL be created

#### Scenario: Checkbox links the Terms

- **WHEN** the registration page is rendered
- **THEN** it SHALL contain a checkbox named `accept_terms` and a link to `/terms/`

#### Scenario: Checkbox sits beside its label

- **WHEN** the registration page is rendered in a browser
- **THEN** the `accept_terms` checkbox SHALL be about 16px wide, not full width
- **AND** it SHALL be left of the label text, with their tops on the same line
