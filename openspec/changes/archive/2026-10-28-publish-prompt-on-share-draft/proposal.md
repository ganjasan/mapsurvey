# Publish prompt when sharing a Draft survey

## Why

The lifecycle step "publish the survey" is not discoverable. A creator builds a
survey, opens **Share**, generates a tracked (UTM) link and distributes it — but the
survey is still in **Draft**. Draft surveys are not publicly reachable
(`check_survey_access()` raises `Http404`), so every external recipient sees a bare
**404**. The creator never notices, because owners/editors bypass `check_survey_access`
and the link opens fine for them: "works for me, broken for everyone else."

Real incident (2026-07-06): a Université Laval client ran a LinkedIn/Instagram/email
campaign for survey "Dorval Odor"; the shared link 404'd for all recipients because the
survey was left in Draft. The link was correct — it was simply never published.

The Share page currently hands out copyable public links regardless of status, with no
warning. This is a discoverability gap, not a bug in access control (the Draft 404 is
intended).

## What Changes

- **Gate the Share page on publish state**: the shareable content (survey link, QR,
  tracking-link form and list) is shown only when the survey is actually reachable by the
  public (`status == 'published'`).
- **Draft/Testing banner**: when the survey is not publicly reachable, the Share page
  shows a status banner explaining that the public link returns a 404 until the survey is
  published, and that only the creator can open it (via Preview).
- **Inline Publish**: owners get a **Publish — open for responses** action right on the
  Share page, reusing the existing `editor_survey_transition` endpoint
  (`draft → published`). Non-owner editors see a "ask the owner to publish" hint instead.
- After publishing, the page reloads and reveals the shareable links.

## Capabilities

### New Capabilities

- `share-publish-gate`: the Share page renders shareable public links only when
  `survey.status == 'published'`; otherwise it renders a status banner plus (for owners,
  when `can_transition_to('published')`) an inline Publish control.

### Modified Capabilities

- `share-page`: shareable sections (survey link, tracking form, tracking list) are
  wrapped behind the publish gate.

## Impact

- `survey/share_views.py`: `share_page` computes `is_shareable` and `can_publish`.
- `survey/templates/editor/survey_share.html`: draft banner + inline Publish; existing
  sections shown only when published.
- Reuses `editor_survey_transition` (`owner`, `require_POST`) — no new endpoint.
- Tests: draft/testing hide links + show banner; owner sees Publish, editor does not;
  published shows the full page.
