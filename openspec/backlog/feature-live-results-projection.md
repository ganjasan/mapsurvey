# Live results projection mode

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-02

## Description

A presentation mode for the analytics dashboard designed for projecting live-updating results at engagement events. Large fonts, high contrast, auto-cycling slides (one question per slide), live response counter, and auto-refresh every 5-10 seconds. Facilitator can pause, skip slides, and filter by question. Minimum response threshold before showing results to avoid premature conclusions.

## Notes

- See [UC-04: Live Results Projection at Event](../docs/use-cases/uc04-live-results-projection.md)
- WebSocket or short-polling for near-real-time updates
- Snapshot export (PDF/PNG) for meeting minutes
- Dark and light themes for different projection environments
- Must show only aggregates, never individual responses
