## Why

A creator reported a star-rating question that shows 5 stars at one time and 10 at another (#452).
Opening an existing stars question in the editor modal seeds the default steps 1–5 before the saved
choices are loaded, so the saved five are appended to five defaults; the next autosave stores ten
entries with duplicate codes, and every further open adds five more. The respondent page draws every
entry. In production 7 of 63 star-rating questions carry duplicate codes.

## What Changes

- The editor modal seeds the five default stars only for a question that has no saved choices; an
  existing question opens with exactly the choices it has.
- Saving a choice list whose codes repeat is refused at the choices stage (editor, autosave, REST/MCP
  `set_choices`) with a message that names the repeated code, so a client-side slip can never be
  stored again. Answers are stored by code, so two options with one code are never meaningful.
- Data: the one affected draft in production is repaired by hand after merge (owner-approved);
  closed test versions are left alone.

## Capabilities

### New Capabilities

### Modified Capabilities

- `rating-question-display`: opening a stars question keeps its choices; duplicate codes are refused.

## Impact

- `survey/templates/editor/partials/question_form_modal.html` (init order of the stars toggle)
- `survey/services/questions.py` (`_parse_choices_json`, `set_choices`)
- Tests in `survey/test_services.py` and the modal template test.
