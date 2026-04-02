# Kiosk mode for event deployment

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-02

## Description

A locked survey display mode for shared tablets at public events. After submission, the survey auto-resets to the start screen for the next respondent. No back-navigation to previous respondent's answers. Optional PIN to exit kiosk mode. Supports intercept surveys at grocery stores, farmers markets, schools, and other community locations.

## Notes

- See [UC-03: Intercept Survey at Public Location](../docs/use-cases/uc03-intercept-survey.md)
- Auto-reset delay configurable (e.g., 10 sec thank-you screen, then reset)
- Kiosk URL parameter: `?kiosk=1&location=farmers-market`
- Location tag recorded with each response for geographic filtering in analytics
- Consider PWA or fullscreen API for true kiosk experience on tablets
