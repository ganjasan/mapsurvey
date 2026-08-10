# Coursework / education channel — "Mapsurvey for classrooms"

**Type**: idea
**Priority**: high
**Area**: general
**Epic**: growth
**Created**: 2026-06-10

## Description

Deliberately court instructors of courses where geo-surveys are a natural assignment (urban planning, GIS / geoinformatics, geography, participatory planning, transport, environmental science). The instructor brings their whole class — every student is simultaneously a respondent AND a creator, which is the only configuration that converts response activity into registrations.

This is the **highest-leverage acquisition play** because it is the one growth pattern the data already proves works.

## Evidence (from 2026-06-10 analysis)

- The **FTSPK class at ITS Surabaya** is the single largest and only repeatable creator-cluster: one lecturer (**Dr. Cahyono Susetyo**, course CP234209 "Sistem Informasi Perencanaan / SIP") → ~30 student registrations + 700+ combined responses, sustained over a month, fully organic.
- **Quantified (2026-06-10 cluster analysis): this one class = 73 registrations on 2026-05-11/12 = 33% of ALL real registrations to date.** It's gmail-based, so it's invisible to email-domain grouping — the dominant growth cluster is temporal, driven by a single course. Replicating even 2–3 FTSPK-like classes would outweigh the entire long tail of one-off signups.
- Genuine multi-person *institutional* clusters are otherwise rare so far (only Decisio ×3 and MIG ×2) — most other "≥2 accounts per domain" are the same person duplicated, not teams. The repeatable lever is classrooms, not scattered B2B.
- Recurring student survey topics — walkability, mobility, "blind spots", accessibility, sidewalk design — are exactly standard urban-planning coursework.
- Many independent academic registrants reinforce the fit: TLU, RMIT, Univ. of Milan, TU Dortmund, Univ. of York, Columbia, UFU Brazil, Al-Azhar, Alexandria, HEPIA, Bauhaus Weimar, Technical Univ. of Crete.

## Scope / plays

- **Warm start**: reach out to Dr. Cahyono Susetyo (lecturer already identified) — understand what made Mapsurvey work for the class, get a testimonial / quote, ask what would make it easier for next semester.
- **Productize for coursework**:
  - Classroom / cohort workspace: an instructor can create a group, invite students, see all their surveys in one place.
  - Assignment templates for the proven topics (walkability audit, mobility survey, accessibility mapping) — ties to [survey template gallery](feature-survey-template-gallery.md).
  - Lightweight "for educators" landing page with the FTSPK story as a case study.
- **Outbound**: build a target list of instructors from the existing academic registrant base + departments matching the proven topics. Personalized outreach (same playbook as the user-outreach campaign).
- **Free-for-education** positioning (already free / open-source — make it explicit for classroom use).

## Notes

- Non-code components (outreach, positioning) can start immediately; product components (cohort workspace) are a later phase.
- Measure lift via [funnel monitoring](feature-funnel-monitoring.md) — tag education-channel registrations.
- FTSPK contact policy: approach via the lecturer, not individual students (see `docs/marketing/user-outreach/ftspk_class/profile.md`).
- Negative guardrail: avoid the "respondent" trap — a class of pure respondents (no creation) would not convert. The value is that students *build* surveys.
- **2026-08-10 — partially shipped.** Landing page and first outreach are live (`survey/templates/for_educators.html:4,102-116`, `docs/marketing/user-outreach/ftspk_class/`). The classroom mechanics — cohort/classroom workspace, assignment templates — are not built.
