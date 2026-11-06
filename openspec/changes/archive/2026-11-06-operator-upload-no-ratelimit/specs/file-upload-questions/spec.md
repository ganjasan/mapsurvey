## ADDED Requirements

### Requirement: Respondent uploads are rate limited per address; operator uploads are not

The upload endpoint SHALL limit uploads to 60 per hour per client IP address and answer `429` with a
respondent-readable message beyond it. An upload that names an operator-entry session which the endpoint
admits (signed-in user with the editor role on the survey, the Pro `operator_entry` feature in force, a
non-online session of the survey's family) SHALL NOT count against or be refused by that limit. All other
validation and the per-session caps SHALL apply to operator uploads unchanged.

#### Scenario: Anonymous uploads are limited

- **GIVEN** 60 uploads from one address in the last hour
- **WHEN** an anonymous respondent from that address uploads another file
- **THEN** the endpoint answers 429 and nothing is stored

#### Scenario: An operator entering paper forms is not limited

- **GIVEN** 60 uploads from one address in the last hour
- **WHEN** an editor uploads a file for an operator-entry session of a Pro workspace from that address
- **THEN** the file is stored and its token returned

#### Scenario: A session that fails the operator gate does not bypass the limit

- **GIVEN** 60 uploads from one address in the last hour
- **WHEN** a request names an online session, or comes from a user without the editor role
- **THEN** the endpoint answers 429
