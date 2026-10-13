## ADDED Requirements

### Requirement: Age and terms confirmation on sign-up

The registration form SHALL include a required checkbox field `accept_terms` labelled "I am 16 or older and accept the Terms of use", where "Terms of use" links to `/terms/`. A submission without it SHALL fail form validation with HTTP 200 and a field error, and SHALL NOT create a user. The honeypot check SHALL still run before form validation, so a bot that fills the honeypot and omits `accept_terms` SHALL still receive the fake-success redirect. Existing accounts SHALL NOT be asked to confirm.

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

## MODIFIED Requirements

### Requirement: Existing registration flow remains intact for legitimate users

A legitimate registration SHALL require the `accept_terms` confirmation (see "Age and terms confirmation on sign-up"); apart from that the change SHALL NOT alter the post-registration behavior for legitimate users. The existing `user_registered` signal handler SHALL still create a personal `Organization` and `Membership`, and the activation email SHALL still be sent in a background thread.

#### Scenario: Legitimate registration still creates personal organization

- **WHEN** a registration with empty honeypot, valid Turnstile token, and below rate limits is submitted with valid form data and `accept_terms` checked
- **THEN** a `User` SHALL be created with `is_active=False`
- **AND** an `Organization` SHALL be created via the existing `user_registered` signal
- **AND** a `Membership` SHALL link the user to the organization with role `owner`
- **AND** the activation email SHALL be sent in a background thread
- **AND** the response SHALL redirect to `django_registration_complete`
