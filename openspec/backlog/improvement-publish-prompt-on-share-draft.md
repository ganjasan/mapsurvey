# Publish prompt when sharing a Draft survey (make "Publish" discoverable)

**Type**: improvement
**Priority**: high
**Area**: frontend
**Epic**: growth
**Created**: 2026-07-06

## Problem

The lifecycle step "publish the survey" is not obvious to users. A creator builds a
survey, opens the **Share** page, generates a tracked link (UTM), and distributes it —
but the survey is still in **Draft** status. Draft surveys are not publicly accessible
(`check_survey_access()` raises `Http404`), so every external recipient sees a bare
**404**.

The creator does not notice, because owners/editors bypass `check_survey_access` — the
link opens fine for them while logged in. So "works for me, broken for everyone else."

The Share page (`survey/share_views.py` → `share_page`) currently lets a user create and
copy tracking links regardless of survey status, with no warning that the link will 404
for the public.

### Real incident (2026-07-06)

Client `ali.ahmadi.2@ulaval.ca` (Université Laval) ran a July 2026 campaign
(LinkedIn / Instagram / email) for survey **"Dorval Odor"**
(`/surveys/02a92b93-ea46-4bbf-bf0b-3d23f0766474/`). The shared link 404'd for all
recipients because the survey was left in **Draft**. The link itself was correct — the
survey was simply never published.

## Desired behavior

When a user tries to **Share** (or copy a tracked link for) a survey that is still in
**Draft**:

1. Explain clearly that the survey is in **Draft**, and that **until it is published it
   is only viewable in Preview** — public visitors will get a 404.
2. Offer to **publish the survey right there** (inline "Publish" action, using the
   allowed `draft → published` transition), instead of forcing the user to hunt for the
   status control elsewhere in the editor.
3. Only present live/copyable public share links once the survey is actually published
   (or clearly mark links as "will work after you publish").

## Scope

- Share page: detect non-public status (`draft`, and consider `testing`/`closed`) and
  render a status banner instead of, or above, the copyable links.
- Inline "Publish" affordance on the Share page (reuse the existing transition endpoint
  `editor_survey_transition`; `draft → published` is already a valid transition).
- Copy explaining Draft vs Preview vs Published, and that only Published surveys are
  reachable at the public `/surveys/<uuid>/` URL.
- Consider the same guardrail anywhere a public survey URL is surfaced to the creator
  (editor dashboard "open survey", QR generation, etc.).

## Notes

- Root cause is discoverability of the Publish step, not a bug in access control — Draft
  404 is intended behavior.
- Related: [Public results map](feature-public-results-map.md) and the public-facing
  survey lifecycle work — implement in the **Public Results Page** worktree
  (`feature/public-survey-results-page`).
- Related: [UTM parameters & link generator](feature-utm-link-generator.md) (the Share
  page this touches).
