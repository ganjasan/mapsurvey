## Why

In the report editor's block list every row carried a small grey pill with the block's internal type key —
`numbers`, `crosstab`, `engagement`. It was left from the old Public results page, is not marked for
translation, and reads as jargon even in English ("crosstab" for a Cross-tab block). After change
`reports-i18n` it was the one English word left in each row of a translated editor.

## What Changes

- A block's row names its type with the type's label ("Key numbers", "Cross-tab", translated), not its key.
- The name sits under the block's title as a second line instead of beside it: the sidebar leaves about
  110 px for both, and a translated name ("Zwei Runden vergleichen") beside the title cut the title to two
  letters.
- A row whose title already is the type's name (a block with no title of its own) shows it once.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reports-editor`: a new requirement — a block's row names its type in the interface language.

## Impact

- `survey/templates/editor/partials/pr_block_list_item.html`, two CSS rules in
  `survey/templates/editor/public_results.html`.
- `survey/tests/test_reports_editor.py`.
