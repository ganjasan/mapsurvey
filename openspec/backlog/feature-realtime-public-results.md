# Real-time updates for public results (live delivery layer)

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: growth
**Created**: 2026-07-04

## Description

A shared delivery mechanism that lets the **public results page** (`/r/<slug>/`, see [public results map](feature-public-results-map.md)) update **live** as new responses arrive — without a manual refresh. This is the technical enabler underneath two existing items that both assume "near-real-time" but don't specify how it's delivered:

- [Live results projection mode](feature-live-results-projection.md) (#21) — the *presentation* consumer
- [Public results map](feature-public-results-map.md) (#27) — the *page* being updated

Scope here is deliberately narrow: **how fresh geometries reach an open browser tab efficiently**, not how they're styled or projected.

## Evidence — the `Tahanan_Padayon` case (2026-07-04)

Survey #334 (`ibmfph`, a Philippine campus-ministry group) revealed an emergent, unplanned use of the platform:

- A **single map, single `point` question**, no text/choices — respondents just drop pins.
- **676 points from 44 sessions** (avg ~15/session; power users dropped 140, 95, 66) — used as a **collaborative pin-wall**, not a survey.
- **74 of 89 sessions arrived in one hour** (2026-07-04 04:00 UTC ≈ noon Philippine time) — a **live event**: everyone opened the map at once.
- The value was **not the dataset** (bare coordinates) but the **live shared visual** — a map of Luzon filling with pins in front of an audience.

Takeaway: people already use Mapsurvey as a *real-time collaborative map for audience engagement*. If a public results page existed and updated live, it would have been the centrepiece of that event. This is a recurring shape (also see [Kiosk mode](feature-kiosk-mode.md) #20, [Live results projection](feature-live-results-projection.md) #21).

## Key decision — webhooks are the wrong layer

A **webhook** pushes an HTTP POST to an *external* system (Zapier, Discord, a customer backend); it cannot update a browser tab. The live page needs **server → browser** delivery:

| Mechanism | Fit | Cost |
|---|---|---|
| **Polling** (HTMX `hx-trigger="every 3s"` / small `fetch` of a GeoJSON endpoint) | ✅ MVP — "map fills over minutes" needs seconds, not ms | none — works on current sync gunicorn / Render |
| **SSE** (server→browser stream) | ⚠️ semantically ideal for "results push" | needs ASGI + long-lived connections; each viewer holds a worker |
| **WebSockets** (Django Channels) | ❌ overkill for a read-only view | Redis channel layer + ASGI |
| **Webhooks** | ❌ not a page-update mechanism | — |

Internally, "new answer arrived" is a Django `post_save` signal on `Answer` — not a webhook. Webhooks only make sense as a *separate* outbound feature (e.g. an OBS overlay or Discord ping at the creator's event).

## Scope (phased)

- **Phase 1 — Polling + cached aggregate (MVP).**
  - `GET /r/<slug>/features.json` returning the aggregated GeoJSON.
  - **Cache the aggregate** (Redis / Django cache), short TTL (3–5s), invalidated on `Answer` `post_save`. This decouples poll rate from DB load: 500 pollers → **1 DB query per TTL window**, not 500.
  - HTMX/JS polling on the results page, merging new features into the map.
- **Phase 2 — Delta endpoint.** `?since=<cursor>` returns only points with `id > cursor`, so payloads stay small as counts grow into the hundreds/thousands (Tahanan already hit 676 in a day).
- **Phase 3 — SSE "presenter mode" (optional).** True push with smooth pin-drop animation + running counter for big-screen event use. Real infra cost (ASGI worker model) — only if Phase 1/2 latency proves insufficient.

## Product framing — separate "live" from "SEO-static"

This item is in **tension** with [public results showcase + SEO](idea-public-results-showcase-seo.md) (#77):

- **SEO showcase** wants a *static, cacheable, indexable* page of finished results.
- **Live/event mode** wants a *maximally fresh* page.

Resolve by making them distinct modes, not one page trying to be both: a static, long-cached, indexable results page by default **+ an opt-in `live` flag** (fresh short-TTL delivery, presenter chrome). Building only the static path would silently foreclose the live use case that the evidence above shows real demand for.

## Notes

- **DB-load caution**: current prod Postgres is `basic_256mb`. The risk is not "real-time" but the **audience** — dozens/hundreds of viewers polling. Caching the aggregate is mandatory, not an optimization.
- **Privacy**: results delivery must stay **aggregate-only**, never individual sessions (same constraint as #21 and `PublicResultsService` k-anonymity masking in #77). Live delivery must not leak per-session data through the delta endpoint.
- **Opt-in**: live mode is a per-survey flag, default off — most surveys want a clean, cacheable, final page.
- Should be implemented through OpenSpec (`/opsx:new`) — touches public endpoints, caching, and a signal on `Answer`.
- Blocks/unblocks: this is a **dependency** of #21 (projection) and a natural extension of #27 (public results map); pairs with #20 (kiosk) at events.
