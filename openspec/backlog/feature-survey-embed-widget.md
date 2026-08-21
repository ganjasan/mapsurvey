# Embeddable survey widget (iframe/script on the customer's own site)

**Type**: feature
**Priority**: high
**Area**: frontend
**Epic**: growth
**Created**: 2026-08-21
**Related**: [Publish launch kit](feature-publish-launch-kit.md) (#132), [AI audience plan](feature-ai-audience-plan.md) (#129), [Share flow dead-ends](improvement-share-flow-private-dead-end.md) (#128)

## Description

Let a creator embed a published survey directly on their own website — an iframe (or
script-tag wrapper) with a copy-paste snippet on the Share page. Every ICP we have
(municipality, chambre d'agriculture, consultancy, university) already owns a site with
an audience; today the only option is sending that audience away to mapsurvey.org.

Referrer data (SurveyEvent, 60 days, 1934 session starts) shows distribution barely
exists: 1230 self-referrals + 695 direct, exactly 1 social and 1 search arrival. The
respondent appears only when the creator personally hands over a link. An embed turns
the customer's existing site traffic into respondents without asking them to run a
campaign — likely the single largest lever on the collection funnel.

## Notes

- Requires revisiting `X-Frame-Options` / CSP for `/surveys/` paths (editor preview
  already uses `@xframe_options_sameorigin` — respondent pages need a deliberate
  allow-from-anywhere posture, or per-survey allowed origins).
- The Leaflet map must survive being embedded at small widths; test the mobile-in-iframe
  case before calling it done.
- Referrer of embedded sessions arrives as the customer's domain — SurveyEvent's
  referrer buckets get their first real "external" segment for free; make sure the
  bucket logic doesn't classify the embedding site as `other`.
- Keep it Free-tier: distribution is the bottleneck for every design partner, and the
  embed on a municipal site is itself "made with Mapsurvey" exposure (viral loop).
