## 1. Editor modal

- [x] 1.1 Seed default stars only for a question without saved choices (`question_form_modal.html`)
- [x] 1.2 Template test: the init seeds defaults only when no saved choices exist

## 2. Server guard

- [x] 2.1 Refuse repeated choice codes in `_parse_choices_json` and `set_choices`
- [x] 2.2 Service tests (GIVEN/WHEN/THEN): editor save and `set_choices` with a repeated code

## 3. Data

- [ ] 3.1 After merge, with owner approval: dedupe the affected production draft
