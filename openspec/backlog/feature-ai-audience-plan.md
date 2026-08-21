# AI audience plan — "how to reach your respondents" report in the publish kit

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: growth
**Tier**: Free (plan preview) / **Pro** (full kit + channel loop)
**Created**: 2026-08-21
**Related**: [AI response triage](feature-ai-response-triage.md) (#95), [AI analytics](feature-ai-analytics.md) (#92), [Share flow dead-ends](improvement-share-flow-private-dead-end.md) (#128), [Workspace plans & entitlements](feature-workspace-plans-entitlements.md) (#87), [Auto-draft public results page](feature-auto-draft-public-results-page.md) (#130)

## Description

When a survey is published, generate an "Audience Plan": an AI report that tells the
creator *who* their respondents are, *which channels* reach them, and *what to send* —
with message drafts in the survey's language, a wave calendar, and one-click creation
of a `TrackedLink` per recommended channel so the plan's channels become measurable.

~90% of creators build and publish a survey but collect near-zero external responses —
the bottleneck is response collection, not the tool. The AI cannot hand the creator a
mailing list, but it can close the *know-how* gap: for geo-surveys the audience is
geographically defined by the map extent, so the channel set (municipality, local
institutions, community hubs) is enumerable from data we already store. Google Forms
has no geography; Maptionnaire has no AI plan. This is a differentiator built on our
own primitives.

## Evidence

Two reports were hand-generated from prod data on 2026-08-21 (session artifacts), both
from nothing but what the platform stores, and both surveys show the identical failure
pattern — a launch-day burst, then silence:

- **Survey 403 "Enquête agricole – ZAP Ansouis"** (Chambre d'agriculture de Vaucluse):
  22 sessions with 109 answers on launch day 2026-08-04, then 10 opens with **zero
  answers**. Question semantics (parcel polygons ×12, irrigation, labels) classify it
  as a *census* → playbook is named-registry coverage (chamber registry, mairie
  co-signature, in-person assistance sessions), not traffic.
- **Survey 440 "Mapa colaborativo LGBT+ em Belo Horizonte"**: 25 sessions on launch day
  2026-08-10 (12 with answers — ~50% open→answer conversion, so the form is fine),
  1 the next day. A community/safety map in a 2.3M city → playbook is snowball through
  trusted nodes (collectives, scene Instagram pages, QR in venues), viral loop via the
  public results page, calendar hook (Dia da Visibilidade Lésbica). Ceiling is
  thousands; actual: 26.
- Matches the standing service-model hypothesis (2026-07-23): every outreach lead
  builds+publishes but gets ~0 real external responses. This feature is the productised
  first artifact of "help collect responses".

## Scope Sketch

The AI infrastructure already exists and was explicitly built for this
(`survey/ai/client.py` docstring: "future AI features (#92/#95)"):

- **Trigger**: transition to `published` enqueues `generate_audience_plan_task`
  (Celery + event-row polling, same pattern as `generate_survey_draft_task`).
  Manual "regenerate" button; `check_quota(org, kind='audience_plan')` seam is ready.
- **Inputs, all from the DB, nothing asked of the creator**: serialized survey
  structure, map center/zoom (pass lat/lon to the model — no geocoder needed),
  languages, creator email domain (institutional signal), session dynamics (for
  relaunch iterations).
- **Structured output** via `complete_structured()`: survey-type classification
  (census / community map / public consultation / academic / B2B) which selects the
  playbook; channel tiers; message drafts *in the survey's language* (report prose in
  the creator's UI language); wave calendar; audience-ceiling estimate.
- **Channel loop — the core idea**: each recommended channel materialises as a
  `TrackedLink` with prefilled `utm_source` in one click. Two weeks later the funnel
  shows per-channel response; regeneration can then say "Instagram works, the mairie
  letter didn't". The plan stops being text and becomes a measured loop.
- **Home**: a tab on the Share page (`survey/share_views.py`) — tracked links and the
  plan belong together; this also resolves half of #128's dead-end (the share page
  finally answers "now what?").
- **Publish kit around the plan** (incremental, non-AI): QR poster PDF, ready-made
  posts, OG share image, `/r/<slug>/` link.
- Ship behind an env-var kill switch (merge reaches prod in minutes).

MVP slice: publish → task → rendered plan on Share tab + "create these tracked links"
+ regenerate. Estimated at a couple of days on the existing AI plumbing.

## Open questions

- **Hallucinated organisation names** (the model names local NGOs/coops from memory).
  V1 mitigation: phrase as "look for organisations like…" + a visible "verify names"
  note. V1.5: Gemini's built-in Google Search grounding is a single request option —
  decide whether grounded names are worth the latency/cost.
- Report language: creator UI language vs survey language — leaning UI language for
  prose, survey language for message drafts (drafted above; confirm with a real user).
- Does regeneration consume quota, and does the plan preview stay free when #87 lands?
  Current lean: preview free (activation hook), full kit + channel-loop iteration Pro.
- Privacy note: inputs are creator-authored content only (no respondent data), but the
  creator's email domain going to the model API should be covered by the same AI
  privacy notice as the draft generator.

## Status

Proposed.
