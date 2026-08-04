# Epic: Growth & User Acquisition

**Description**: Features and go-to-market plays aimed at acquiring and activating new *survey creators* (not just respondents). Grounded in the 2026-06-10 funnel analysis (see below): registration growth is NOT driven by raw response volume — it is driven by surveys whose audience overlaps with the creator population (e.g. a university class), and by plugging the activation leak (high-value signups that never return).

**Created**: 2026-06-10

## Key finding that motivates this epic (2026-06-10 analysis)

Weekly time-series (Feb–Jun 2026) of new signups vs. user-survey responses:

- `corr(signups, user_sessions)` synchronous = **+0.58**, but drops to **−0.03** once the single FTSPK-class week (2026-05-11) is removed → the entire positive correlation is one external event.
- Lag test `corr(signups[N], user_sessions[N−1])` = **−0.09** → taking a survey does **not** precede registering. No causal "respond → register" signal.
- Decisive counterexample: week 2026-03-30 had **614 responses** (Lyon transit survey going viral) but only **7 signups** — one of the lowest. General-public respondents do not convert to creators.

**Refuted hypothesis**: "more responses → more registrations."
**Working hypothesis**: growth happens where the *survey audience = potential creators* (a class, professional peers), via social clusters. Observed clusters: FTSPK class (~30 students, 1 lecturer, 700+ responses), Decisio (3 colleagues), MIG Inc. (2), Dutch Vriendenweekend (friends — note: respondents did NOT convert, a negative example).

## Follow-up analysis (2026-06-10) — four hypotheses tested on current data

**Activation funnel** (222 real registrations): created a survey **117 (53%)** → added ≥1 question **85 (38%)** → got ≥1 response **74 (33%)** → ≥5 **48 (22%)** → ≥10 **36 (16%)**.
- The leak is at the TOP: ~47% never create a survey; those who reach a real question almost all get responses (85→74 = 87%). Response collection is not the problem — reaching a first built survey is. → strengthens [survey template gallery](../feature-survey-template-gallery.md).
- Side finding: 74 collected responses but only 42 formally "published" — responses arrive on draft/testing via test links; the publish step is underused.

**Cluster dominance**: 78% of registrations are free-mail, 22% institutional. The dominant cluster is **temporal, not domain-based**: the FTSPK class = **73 signups in 2 days (33% of all registrations)**, all gmail. Genuine multi-person institutional clusters are rare (Decisio ×3, MIG ×2); most "≥2 per domain" are duplicate accounts of one person. → strongly reinforces [coursework channel](../idea-coursework-education-channel.md) as THE lever, and surfaced [account-dedup / signup UX friction](../improvement-account-dedup-signup-ux.md).

**Geo-input friction** (respondent side): geo questions are the most-skipped substantive type — point 32%, line 31%, polygon 16.5% answer-rate vs 40–48% for non-geo. → new item [reduce geo-input friction](../improvement-reduce-geo-input-friction.md).

**Survey length → completion**: inconclusive / confounded. No clean monotonic length effect; audience motivation dominates. Full completion is low across the board (12–35%). Do NOT treat "shorten surveys" as a growth lever — the driver is question type (geo), not count.

## Items in this epic

**Acquisition:**
- [Coursework / education channel — "Mapsurvey for classrooms"](../idea-coursework-education-channel.md) — highest-leverage, proven by FTSPK
- ["Made with Mapsurvey" viral loop on public pages](../feature-made-with-mapsurvey-viral-loop.md) — cheapest compounding loop
- [Public results showcase gallery + SEO](../idea-public-results-showcase-seo.md) — organic acquisition via indexable results pages
- [Localized growth in markets with existing traction](../idea-localized-growth-markets.md) — NL / FR / IT / ID / DE

**Activation (the 3-layer stack — see below):**
- [AI survey-creator agent](../idea-ai-survey-creator-chat-agent.md) — highest-ceiling core
- [Interactive onboarding](../idea-interactive-onboarding.md) — guided wrapper, drives publish/share
- [Survey template gallery](../feature-survey-template-gallery.md) — seed library + cheap fallback/baseline

**Adjacent UX fixes surfaced by the funnel analysis:**
- [Reduce geo-input friction](../improvement-reduce-geo-input-friction.md) — geo is the most-skipped respondent question type
- [Account-dedup / signup-login UX](../improvement-account-dedup-signup-ux.md) — duplicate accounts signal signup friction

## Activation stack: template → onboarding → AI agent

The activation leak (47% of registrations never create a survey) is attacked by three complementary layers, NOT competitors:

| Layer | Role | Build cost / risk | Converts |
|-------|------|-------------------|----------|
| Template gallery | seed/few-shot library + deterministic fallback | low / low | baseline (clone still leaves near-blank editor) |
| Interactive onboarding | guided wrapper; offers AI/template/blank; drives draft→publish→share | medium / medium | likely > template alone |
| AI survey-creator agent | generates a personalized working draft from a chat description | high / high (cost, abuse, geo-quality) | highest ceiling |

**Honest caveat**: we cannot yet prove the ordering AI > onboarding > template on conversion — there's no funnel instrumentation or A/B. The disciplined sequence:

1. Ship [funnel monitoring](../feature-funnel-monitoring.md) + referrer/UTM → get a measured baseline.
2. Ship the cheap scaffolding (template + onboarding) → de-risk, immediate lift, baseline to beat.
3. Ship the AI agent as flagship → measure lift against that baseline.

The AI agent must be **geo-aware** (bias to `point`, avoid polygon-heavy output) given that geo is the most-skipped respondent question type — otherwise it generates surveys that look done but don't collect.

## Hard prerequisite (cross-epic)

Acquisition measurement is currently blind. Before scaling any channel, ship [Funnel monitoring](../feature-funnel-monitoring.md) + [Referrer tracking](../feature-referrer-tracking.md) + [UTM link generator](../feature-utm-link-generator.md) (survey-analytics epic) so we can attribute registrations to channels rather than guessing.

Email deliverability is the campaign's single biggest dependency, and bot signups are degrading SMTP reputation — the [abuse-prevention](abuse-prevention.md) Phase 1 (Turnstile + rate-limit + honeypot) is a prerequisite for any email-driven growth.
