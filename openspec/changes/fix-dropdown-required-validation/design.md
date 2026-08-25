# Design: fix-dropdown-required-validation

## Context

`ChoiceDropdownWidget` keeps a native `<select name=...>` as the real control and hides
it (`choice_dropdown.html`), showing a search input plus a filterable `<ul>`. The select
is populated from the question's choices, whose codes start at 1, and carries `selected`
only when an answer already exists.

An HTML `<select>` with no `selected` option and no blank entry is not "empty" — the
browser selects the first option. So the widget starts life holding a value nobody
chose. The respondent form is `novalidate` and runs its own required check in
`base_survey_template.html` (`htmx:configRequest`), which asks whether any
`input/textarea/select` inside a `[data-required="true"]` card has a non-empty value.
That check is satisfied by the phantom value, so the section submits and stores it.

## Goals / Non-Goals

**Goal**: an untouched dropdown submits nothing, and the existing required machinery
treats it exactly like an unanswered radio question.

**Non-Goals**: server-side answer validation (the `initial=request.POST` path);
reworking the client-side required check; touching other display styles.

## Decisions

### D1. A blank option in the select, not JS that clears the value

The fix belongs where the wrong value is born. A `<option value="" selected>` placed
first whenever nothing is stored makes the select genuinely empty, which:

- makes the app's own required check correct with no change to it;
- makes the POST omit the answer (empty string), so nothing is stored;
- costs nothing on the visible side — the option list the respondent sees is the `<ul>`,
  which is built separately and never shows the placeholder.

Rejected: clearing `select.value` from JS on load. It would leave the markup lying about
its state (a page rendered without JS, or before the script runs, still holds the
phantom value), and any future code reading the select before the fix-up would see the
same wrong answer. The bug is in the rendered document, so it is fixed in the document.

Rejected: making the required check smarter (e.g. ignore `.cd-select`). It would fix the
button but not the stored answer — the POST would still carry `=1`.

### D2. Guard the storage path against an empty choice value

With a blank option present, an optional dropdown left alone posts `code=""`.
`survey_section`'s POST loop treats a non-empty `getlist` as an answer, so it would try
to store `""` as a choice. Empty strings are dropped before the choice branch, which
also protects every other control that can post an empty value.

### D3. Tests aim at the two things that actually failed

- Rendered markup: a dropdown with no stored answer contains a selected blank option;
  one with a stored answer selects that option and no placeholder is selected.
- Storage: a POST that omits the value stores no answer for the question — the assertion
  that would have caught the original defect.

Both are cheap and neither needs a browser. The client-side required check remains
browser-verified by hand (tasks), as it is jQuery on a page the test client never runs.

## Risks / Trade-offs

- A blank option is now part of the select's DOM; anything iterating options must expect
  it. The visible list (`<ul>`) is built from the same loop, so the placeholder is
  excluded there explicitly.
- Existing sessions that already stored a phantom first choice are not rewritten. On the
  Olney demo those rows are demo traffic; cleaning them is a separate, explicit step.

## Migration Plan

None. Effective on next render for every dropdown question.

## Open Questions

None.
