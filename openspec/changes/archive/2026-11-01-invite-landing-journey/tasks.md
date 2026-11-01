## 1. One acceptance path

- [x] 1.1 `survey/invitations.py`: `SESSION_TOKEN_KEY`, `JOINED_KEY`, `acceptable`, `remember`,
      `pending`, `accept(invitation, user, request=None, surface=…)`, `accept_pending`,
      `join_by_address(user, request=None)`, `take_joined` (design D1, D7); `accept` emits
      `invitation_accepted` (`product_events`: organisation id, role, surface).
- [x] 1.2 `org_views.accept_invitation`: signed-in branch calls `invitations.accept(…, surface='link')`;
      the flash message goes; redirect to `editor` unchanged.
- [x] 1.3 `middleware.ActiveOrgMiddleware`: parked token → `invitations.accept_pending(request, request.user, surface='sign_in')`;
      the private `_process_pending_invitation` is gone.
- [x] 1.4 `signals.accept_invitations_for_email` → thin alias of `invitations.join_by_address`
      (keep the name for callers/tests) and `accept_invitations_on_confirmation` passes `request`.

## 2. Registration through an invitation

- [x] 2.1 `signals.create_personal_org_on_registration`: `accept_pending(request, user, surface='register')`
      first; return without a personal org when it joined (D2).
- [x] 2.2 `AbuseProtectedRegistrationView`: GET `?invite=<token>` → `acceptable` → `remember`,
      `invitation` in context, `get_initial()` email; template subtitle "Create an account to join
      <workspace>." (D3).
- [x] 2.3 `org/invitation_landing.html`: *Create account* → `?invite=<token>`, *Sign in to accept* →
      `?next=<accept URL>`; `{% trans %}` on every string.

## 3. Landing on the dashboard

- [x] 3.1 `views.editor`: `take_joined` → `joined_org` (only when it is the active workspace), skip the
      start redirect on that render; `editor_sees_none` for the editor empty state (D4, D5).
- [x] 3.2 `editor.html`: joined banner (dismissible, above the list; editor sentence); the two empty
      states share `editor/partials/_dashboard_empty_text.html` — editor variant naming the
      workspace, default text under `{% trans %}`.
- [x] 3.3 `DirectActivationView.post`: sign in first (`_sign_in`), then `user_activated`, then
      redirect (D6).

## 4. Tests (GIVEN / WHEN / THEN)

- [x] 4.1 New `survey/tests/test_workspace_invitation_journey.py` (25 tests): journeys A (link →
      register), B (direct registration, personal workspace, no join), C (confirmation → joined
      workspace active, banner, also with another account signed in); landing links; register page
      pre-fill, expired and garbage `invite`; dead-token fallback to a personal workspace; different
      address on the form; banner once / only for the active workspace / no editor sentence for an
      admin; editor empty state vs owner default vs editor with a survey; event surfaces.
- [x] 4.2 `test_org_access_control.py`: invitation tests pass unchanged through the one path (none
      asserted the flash message).
- [x] 4.3 `test_registration_abuse_defenses.py`: unchanged, passes (no invitation → personal
      organisation); the "with invitation → none" scenario is 4.1.
- [x] 4.4 `test_sign_in_grace_period.py`: unchanged, passes with the new activation order; the
      "confirmation lands in the joined workspace" scenario is 4.1.
- [x] 4.5 `test_test_suite.py`: `workspace-invitation-journey` listed in `UNMAPPED_MODULES` until the
      archive creates `openspec/specs/workspace-invitation-journey/` (the archive chore removes the line).

## 5. Strings, changelog, docs

- [x] 5.1 Five creator strings appended to the ten offered catalogs and compiled;
      `survey.tests.test_ui_internationalization` green.
- [x] 5.2 `survey/changelog/2026-10-31-invited-colleagues-land-in-your-workspace.html` (`kind: fixed`).
- [x] 5.3 CLAUDE.md: "Workspace invitations" paragraph (one acceptance path, no personal workspace,
      the activation order).

## 5a. Owner review of the dashboard screenshot (2026-11-01)

- [x] 5a.1 The search field, "+ New Survey" and ⋯ share one shape: 40 px high, 8 px radius,
      one border weight (≥1024 px), 44 px in the 768–1023 row and on the phone; `editor.html`
      CSS only. Checked at 1280 / 900 / 390 px; `test_editor_mobile_navigation`,
      `test_dashboard_layout`, `test_survey_start_chooser` green.

## 6. Verification

- [x] 6.1 `./run_tests.sh survey.tests.test_workspace_invitation_journey survey.tests.test_org_access_control survey.tests.test_registration_abuse_defenses survey.tests.test_sign_in_grace_period survey.tests.test_survey_start_chooser survey.tests.test_ui_internationalization survey.tests.test_test_suite survey.tests.test_in_app_changelog` — 244 tests, OK.
- [x] 6.2 Full `./run_tests.sh survey billing api mcp newsletter` — 3678 tests, OK (2026-10-31).
- [x] 6.3 Dev stack (Playwright, port 9020): invitation link signed out → *Create account* →
      register page says "Create an account to join Team Org." with the address pre-filled →
      dashboard with the "You've joined Team Org." banner and the editor's empty state; the
      workspace switcher lists Team Org only. The banner's editor sentence is left out when the
      empty state already says it (seen as a duplicate on this screen; spec amended).
