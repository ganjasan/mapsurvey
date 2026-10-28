## ADDED Requirements

### Requirement: Every test starts in the default language
The project test runner SHALL make the default language (`LANGUAGE_CODE`) the active one before
each test, so a language activated by an earlier test in the same process cannot change what a
later test reads.

#### Scenario: Earlier test left another language active
- **WHEN** a test activates Portuguese and does not reset it, and the next test in the same
  process renders a translatable label without making a request
- **THEN** the label is in the default language
