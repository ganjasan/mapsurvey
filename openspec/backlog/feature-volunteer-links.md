# Volunteer links — per-person tokenised survey links

**Type**: feature
**Priority**: high
**Area**: backend
**Created**: 2026-08-23

## Description

A campaign owner generates one link per volunteer (`?v=<token>`). The token tags every
session that volunteer creates, optionally presets their assigned area/zone, and is the key
that makes resume possible (FD-3). No account, no password, no per-user licence — the link
IS the identity.

Today sessions are anonymous, so "who collected this" does not exist in the model. Olney
works around it with a required zone dropdown; any campaign with per-person accountability
(routes, quotas, quality follow-up) cannot be run at all.

## Notes

- Model: a `Collector`/`CampaignParticipant` row per token, FK from SurveySession. Must NOT
  reuse the platform User model — volunteers are the customer's people, not our accounts
  ([[project-posthog]] boundary logic applies here too: their people stay their data).
- Owner-side UI: a table of volunteers with link, assigned zone, sessions collected, last seen.
- Bulk generation + printable/QR handout is what a clerk actually needs on count morning.
- Epic: field-data-collection (FD-2)
