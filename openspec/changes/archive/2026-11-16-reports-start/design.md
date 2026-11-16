## Context

Since `reports-story` a report is a list of blocks edited on its own; since `reports-live-blocks`
it has engagement, cross-tab and live numbers. `scaffold_report` already drafts a survey's first
report (one block per question) when the Public results tab opens. Hand-made reports open with key
numbers and "how the survey ran", follow the questionnaire's order, and end with what happens next.

## Decisions

1. **A draft is a new report, never the survey's first one.** The first report is what the thanks
   page and the Share page link; drafting into it would change a page that may be public.
2. **Rules, one module.** `reports/drafting.py` holds the question walk (`_questions`: answered,
   in respondent order, each with a block kind) and four small builders over a `_Draft` that
   appends blocks. A template is a function, not data: four arrangements do not justify a schema.
3. **Hidden instead of placeholder.** Prompts and candidate quotes are real blocks with
   `is_hidden=True`: the author sees them in the outline with the eye-slash mark, a visitor never
   does, and publishing an unfinished draft is harmless. This is also how "a quote appears only
   after the author picked it" holds for drafted quotes.
4. **Candidate quotes are chosen by a plain rule** — the most recent distinct answers between 30
   and 320 characters, at most eight. No ranking model; the author picks.
5. **No automatic cross-tab.** Which two questions to cross is a judgement; the kits always did it
   on request. The block is one click away.
6. **Copy = export + import.** `copy_report` runs the report file's round trip in memory, so a
   copy cannot keep something an export would lose. #711 (copy and compare rounds) builds on it.
7. **One card, one click.** Each card is the submit button of its own form; the survey is chosen
   once above the draft cards (a GET that reloads the page), the copy card carries its own select
   and button because it needs a choice.
8. **Entry on Responses is a button for every published survey**, not a banner at closing: 11 of
   16 hand-made reports were asked for while the survey was still open.

## Risks / Trade-offs

- [A draft of a long survey is long] → that is the point of "cut it down"; delete is one click.
- [Drafting copies free-text answers into a report row] → hidden, unpublished, inside the same
  workspace that already reads them on Responses.

## Migration Plan

`reports/0005`: `Report.template`. Rollback: revert.
