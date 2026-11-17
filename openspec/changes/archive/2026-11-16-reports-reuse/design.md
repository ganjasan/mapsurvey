## Context

`drafting.copy_report` is the report file's round trip (export + import in memory). The file names
each data block by survey uuid + question code; import re-binds by code and writes a note for what
it cannot bind. Chart payloads come from `ReportService._choice_data` / `_number_data`, per block
survey (`_scope_of`).

## Goals / Non-Goals

**Goals:** a copy onto round two needs no manual rebinding; unmatched blocks are named; one
question can be shown for two rounds in one block.

**Non-Goals:** matching questions whose code changed (codes are the contract between rounds, as
they are between versions); comparing more than two rounds; comparing maps; significance tests.

## Decisions

- **Rebinding is the import's own**: `import_report(..., onto=survey)` resolves every block's
  survey to `onto`, whatever the file says. One code path for import, copy and copy-onto.
- **Unmatched → a hidden text block**, in the block's place, saying what was there ("Chart
  “Top priority” (PRIO): this survey has no such question"). Hidden blocks never reach the page
  (the #705 rule: hidden instead of placeholder), the author sees them where the story has a hole,
  and the pre-publication checks already count hidden blocks. A plain import (no `onto`) keeps its
  behaviour: the block is left out and named in the notes.
- **The copy card** gets one more select, "for the survey", defaulting to "the same surveys"; still
  one form, one button.
- **Compare is a question block with a second survey**: `block_type='compare'`, `dataset` +
  `question_code` as a chart's, `config = {"other": "<survey uuid>"}`. The payload is two chart
  aggregations by the existing functions, joined by option code: per round the number of people
  who answered and, per option, the share. K-masking is each round's: a masked option shows "<K"
  and no share; a round with fewer than K respondents shows no shares at all. Number questions
  compare count, average and median.
- **Shares, not counts, are what is compared** (rounds differ in size); the count of respondents
  per round is shown in the column head.
- The page draws it as an HTML table with two CSS bars per row — no chart library, so the PDF, the
  CSV and the page read the same rows (`tables.rows_of`).
- `report_reused` fires for a copy (`onto` or not): `source`, `report`, `onto` (bool), `blocks`,
  `unmatched`.

## Risks / Trade-offs

- A code reused for a different question in round two compares apples and pears → the block shows
  both surveys' names and the question's wording from the report's survey; options are joined by
  code and an option one round lacks reads "—".
