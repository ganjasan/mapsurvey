# Show response count in editor dashboard

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-03-26

## Description

Show the number of responses (sessions) per survey on the /editor/ dashboard. Currently the dashboard lists surveys but gives no indication of how many people have responded.

## Notes

- Source: Marijana Jericevic (Galanthus) — unsolicited follow-up, she came back on her own to suggest this
- Quick win — just a COUNT query on survey_surveysession joined to the dashboard view
- Every survey creator wants this. Basic expectation from any survey tool
