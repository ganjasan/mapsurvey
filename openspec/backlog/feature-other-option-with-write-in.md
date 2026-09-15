# Native "Other, please specify" write-in option on choice questions

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-09-02

## Description

Let a creator mark one option of a `choice`/`multichoice` question as "Other" with an
attached free-text input that appears when that option is selected. Today the workaround
is an "Other" choice plus a separate conditional text question (visibility rule "show
when Other selected") — it works for both single and multiple choice, but the write-in
exports as its own CSV column instead of landing in the parent question's column, and it
costs the creator two questions per "Other".

## Notes

- Requested 2026-09-02 by Megan Critchley (BC3 Research,
  [correspondence](../../docs/marketing/user-outreach/bc3_megan/correspondence/2026-09-02_reply-two-question-screening-and-other-option.md));
  she was given the conditional-question workaround.
- Standard feature in Google Forms / SurveyMonkey / Maptionnaire — parity item.
- Export design is the real work: the write-in text belongs with the parent question's
  answer (e.g. `Other: <text>` in the same column, or a paired `<question>_other` column),
  and the aggregated results page must bucket "Other" without leaking individual free
  text (k-anonymity rules in `public_results.py`).
- Touches: `choices` JSON schema, `SurveySectionAnswerForm`, respondent template + JS
  toggle, CSV export, ZIP serialization, editor choice UI.
