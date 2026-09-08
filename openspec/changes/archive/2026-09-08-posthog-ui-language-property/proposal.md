## Why

The creator interface was localised on 2026-08-29 to raise activation for non-English creators,
and the AARRR dashboard carries an annotation for it — but no number can be put next to it: PostHog
knows nothing about which language a creator uses. `CreatorPreferences.ui_language` holds the
answer in our database and is never forwarded.

## What Changes

- The creator's interface language becomes a PostHog person property `ui_language` (`''` when the
  creator follows the browser), set live when the preference is saved and backfilled for existing
  creators by `sync_posthog_person_properties`.
- Insights on the AARRR dashboard can break activation down by `ui_language`.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `product-analytics`: identified creators carry their interface language as a person property.

## Impact

`survey/product_events.py` (one helper), `survey/editor_views.py` (one call in
`set_creator_language`), `survey/management/commands/sync_posthog_person_properties.py`,
`survey/tests.py`. No migration. Privacy boundary unchanged: a UI language is a creator preference,
not respondent data, and it is what the creator already sees in the header.
