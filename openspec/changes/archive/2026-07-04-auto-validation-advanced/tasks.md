## 1. Service Layer

- [ ] 1.1 Rule: fast completion — session_start to survey_complete < 30 seconds (via SurveyEvent timestamps)
- [ ] 1.2 Rule: duplicate sessions — same user_agent within 1 hour for same survey
- [ ] 1.3 Add both rules to `compute_session_issues()`
- [ ] 1.4 Add 'fast' and 'duplicate' to issues filter dropdown options

## 2. Tests

- [ ] 2.1 Test fast completion detected
- [ ] 2.2 Test normal-speed session not flagged
- [ ] 2.3 Test duplicate sessions detected
- [ ] 2.4 Test unique user agents not flagged as duplicate
