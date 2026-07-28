# Rating question clips text labels

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-07-28

> **Promoted to the OpenSpec change `fix-geo-form-ui` on 2026-07-28 and fixed there.**
> The CSS now sizes rating options to their content and wraps long labels.

## Description

A `rating` question whose choices are words instead of numbers renders unreadably: every
option is forced to the same width and the label is cut off mid-word. With five options
like "very unsure / rather unsure / undecided / rather confident / very confident" the
respondent sees "very unsur", "rather unsur", "undecid", "rather confide", "very confident".

The option text is never wrapped and never truncated gracefully — it simply overflows its
box. Any survey author who builds a Likert scale with worded anchors (the most common form
of a rating scale) hits this.

## Root cause

`survey/assets/css/main.css:325`

```css
.question-card--rating > div > div {
  flex: 1;
  min-width: 0;
}
```

- `flex: 1` resolves to `flex-basis: 0`, so all options get **identical width regardless of
  label length**, driven by the container, not the content.
- `min-width: 0` allows each cell to shrink below its content width.
- The label (`.question-card--rating label:has(input[type="radio"])`, line 330) sets
  `flex-direction: column` and `text-align: center` but no `overflow-wrap` / `hyphens`, so
  long words neither wrap nor break.
- `flex-wrap: wrap` on the parent (line 320) does not help: it wraps *items*, and items with
  a zero flex-basis always fit on one line.

The widget itself is a plain `forms.ChoiceField` + `RadioSelect` (`survey/forms.py:212-214`),
so nothing constrains label length at the form layer either.

## Reproduce

1. Create a question with `input_type: rating`.
2. Give it 5 choices with worded labels, e.g. "very unsure" … "very confident".
3. Open the survey on a desktop viewport — labels are clipped.

Live example while it lasts: the ThINK demo survey,
`user_surveys/waermeplanung_quedlinburg_demo/`, section "Your view of the neighbourhood".

## Proposed fix

Rating scales with worded anchors are standard in survey tooling, so the fix should make
them a first-class case rather than telling authors to use numbers:

1. **Let the content drive the width.** Replace `flex: 1; min-width: 0` with something like
   `flex: 1 1 auto; min-width: min-content`, and add `overflow-wrap: anywhere` (or
   `hyphens: auto`) on the label so long words wrap instead of overflowing.
2. **Wrap to a second row** when the labels genuinely do not fit — `flex-wrap: wrap` already
   exists and starts working once the basis is content-driven.
3. **Consider the anchor-label pattern** used by Qualtrics/SurveyMonkey for long scales:
   numbered buttons `1 … 5` with the worded poles printed under the two ends. Cleaner than
   five long labels at any viewport, and it keeps the numeric coding in the data.
4. **Fall back to a vertical list** when labels exceed a length threshold — at some point a
   horizontal segmented control is the wrong control.

## Notes

- Test at mobile width as well; the desktop case is already broken, mobile will be worse.
- Related: the same survey exposed [Sub-question popup is too narrow](bug-subquestion-popup-too-narrow.md).
