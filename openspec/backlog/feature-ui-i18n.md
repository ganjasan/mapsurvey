# Translate UI buttons and instructions

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-03-26

## Description

Translate interface elements visible to survey respondents: "Next" button, "Draw polygon", "Draw line", "Draw point" instructions, and other UI text. Currently these are hardcoded in English even when the survey content is in another language.

## Notes

- Source: Manuel Frost (manu04) — his survey is in German but buttons and map instructions are in English
- Django i18n infrastructure exists, needs to be applied to survey-taking templates and Leaflet draw controls
