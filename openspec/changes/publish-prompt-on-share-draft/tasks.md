# Tasks — publish-prompt-on-share-draft

## 1. Backend

- [x] 1.1 `share_page` (`survey/share_views.py`): compute `is_shareable = survey.status ==
      'published'` and `can_publish = survey.can_transition_to('published')[0]`; pass both
      to the template (keep `effective_role` in context)

## 2. Template

- [x] 2.1 `survey_share.html`: when `is_shareable` is false, render a status banner
      (draft/testing/closed copy) explaining the public link 404s until published
- [x] 2.2 Inline **Publish — open for responses** button in the banner, shown only when
      `effective_role == 'owner'` and `can_publish`; non-owner editors get an
      "ask the owner to publish" hint
- [x] 2.3 Wrap the existing shareable sections (Survey link, Track where responses come
      from, Your Tracking Links) so they render only when `is_shareable`
- [x] 2.4 `publishFromShare()` JS: `fetch` POST `status=published` to
      `editor_survey_transition` with the CSRF token, then `location.reload()` on success

## 3. Verification

- [x] 3.1 Test: draft survey → Share hides the links and shows the banner
- [x] 3.2 Test: owner sees the inline Publish control; a non-owner editor does not
- [x] 3.3 Test: published survey → Share shows the full shareable page (no banner)
- [x] 3.4 Test: testing survey → banner shown, links hidden
- [x] 3.5 Full `./run_tests.sh survey` green
- [x] 3.6 Manual: draft survey → publish inline → page reloads with links unlocked
