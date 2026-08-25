# Proposal: fix-dropdown-required-validation

## Why

A `choice` question rendered as a searchable dropdown submits its **first option** when
the respondent never touched it. Not a missing-validation gap — a silently wrong answer.

The hidden `<select>` behind the widget has no blank option and nothing marked
`selected`, so the browser auto-selects index 0 the moment the page renders. From then
on everything downstream behaves as if the respondent had chosen it:

- the app's own required check (`base_survey_template.html`, "is any input/select in
  this card non-empty") sees `value="1"` and passes the card as answered — which is why
  the forward button submits a form the respondent left empty;
- the POST carries `<code>=1` and an answer for the first choice is stored.

Found on the live Olney demo (2026-08-25): of four answers to "Which counting area are
you covering?", three are `[1]` — the first option — against 25 sessions. For that
survey the zone is what makes every observation in the session attributable, so the
damage is not a blank field but a plausible wrong one.

Radio rendering is unaffected (nothing is checked by default), so this arrived with the
dropdown display style. Server-side validation would not have caught it either: the
section POST path builds the form with `initial=request.POST` and never binds data —
the standing "answers never validated server-side" gap, out of scope here.

## What Changes

- The dropdown's hidden `<select>` gets a blank placeholder option, selected whenever
  the question has no stored answer. An untouched dropdown therefore submits nothing,
  the required check sees an empty card and blocks the forward button, and no phantom
  first-choice answer is recorded.
- Submission of an empty value for a non-required dropdown stores no answer (guard on
  the POST path, so an optional question left alone stays unanswered rather than
  becoming a blank row).
- Tests assert on rendered markup and on what a POST actually stores, since neither the
  browser default-selection nor the client-side required check is exercised by the
  existing suite — which is exactly why this shipped green.

## Capabilities

### Modified Capabilities

- `choice-dropdown-display`: an untouched dropdown SHALL submit no value, and a required
  one SHALL block the section the same way an unanswered radio question does.

## Impact

- `survey/templates/choice_dropdown.html` — blank placeholder option.
- `survey/views.py` — skip empty choice values when storing answers.
- `survey/tests.py` — markup and storage tests.
- No migration. Existing stored answers are not rewritten by this change; the four
  suspect rows on the Olney demo are demo data and are cleaned separately.
