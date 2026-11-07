## Why

The sidebar's *What's new* block showed a pending hero (the 2026-10-26 assistant entry) in place of
every card entry shipped after it, for up to 30 days. The owner asked on 2026-11-07 for the sidebar
to show the newest entry.

## What Changes

- The block shows the newest unseen entry. A pending hero wins only when no card entry newer than
  it is unseen. Closing still moves the watermark over everything shown.

## Capabilities

### New Capabilities

### Modified Capabilities
- `changelog-hero-banner`: a newer card entry is shown in place of an older pending hero.

## Impact

`survey/context_processors.py::whats_new`, one test. No template change.
