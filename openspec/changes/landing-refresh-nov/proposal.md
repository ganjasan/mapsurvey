## Why

The homepage was last rewritten in mid-October. Since then the product shipped paper forms (print,
then photos of filled-in sheets back to responses, map marks included — #489, #495), operator entry
for interviews (#355), embedding on another site (#284), the REST API and MCP server (#380, #306),
the spray area and coverage map, the cluster map (#563), map styles (#545), the Translations tab
(#454) and survey periods (#497). None of it is on the page, and paper is the answer to the question
every municipality asks first: "and the people who will not open a link?"

## What Changes

- The capabilities grid grows from six cards to nine: **Paper forms and interviews**, **On your own
  site**, **Works with your AI agent**.
- Existing cards and showcase steps name what shipped since: spray area, map styles, translations
  tab, open/close dates, cluster and coverage maps, paper.
- The Researchers and Municipalities use-case cards mention the API/MCP and paper/embedding.
- Every new homepage string gets its Russian translation (`/ru/` twin).
- No prices, no hosting claims; plan limits are not stated on the homepage (the Pro page owns them).

## Capabilities

### New Capabilities

### Modified Capabilities
- `landing-page`: the capabilities grid holds nine cards.

## Impact

`survey/templates/landing.html`, `survey/locale/ru/LC_MESSAGES/django.po|mo`,
`survey/tests/test_landing_page.py`. No screenshots change.
