## 1. Fix

- [x] 1.1 Set `use_required_attribute = False` on `SurveyBriefForm` with a comment naming the shared-form reason
- [x] 1.2 Confirm the rendered brief fields no longer carry `required`, and that `form.name` (SurveyCreateForm) keeps it

## 2. Tests

- [x] 2.1 `action=empty` with a blank brief creates the survey and redirects to its editor
- [x] 2.2 The rendered create page contains no `required` attribute on any brief field
      — verified to fail without the fix (the pre-existing manual-path test does not,
      because the test client never runs browser validation)
- [x] 2.3 `action=generate` with a blank `goal` still returns the invalid-brief fragment and creates no `AIGenerationEvent`
      — already covered by `test_generate_without_a_goal_redisplays_the_form`

## 3. Verify

- [x] 3.1 Run the survey test suite — 1371 tests, OK (1 skipped)
- [x] 3.2 Drive the real page: click "Create empty" with an untouched brief and land in the editor
      — done in a real browser (Playwright) against a local stand with the AI panel rendered:
      form `checkValidity()` is true with a blank brief, the click lands in the new survey's
      editor, and re-adding `required` to `#id_goal` reproduces the production symptom
      (click swallowed, URL unchanged). "Generate draft" with a blank goal returns
      "What do you want to find out?: This field is required." into the status slot.
