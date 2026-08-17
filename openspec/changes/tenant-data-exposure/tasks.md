## 1. Remove the public survey listing

- [x] 1.1 Delete the `survey_list` view (`survey/views.py:555-558`). Leave the identically
      named local variable in the `editor` view (`survey/views.py:481-540`) untouched.
- [x] 1.2 Delete `survey/templates/survey_list.html`.
- [x] 1.3 Replace the route in `survey/urls.py:106` with
      `RedirectView.as_view(url='/', permanent=True)`, keeping the URL name `survey_list`
      free or removing it — confirm nothing reverses it first.
- [x] 1.4 Remove the `/surveys/` entry from `sitemap_xml` (`survey/views.py:1795`). Leave
      the `/surveys/<uuid>/` loop and `Allow: /surveys/` in `robots_txt` alone.
- [x] 1.5 Confirm the tree is clean: `grep -rn "survey_list" survey/ mapsurvey/` returns only
      the `editor` view's local variable and unrelated test locals.

## 2. Authorize the response export

- [x] 2.1 In `download_data` (`survey/views.py:1027`), after `resolve_survey`, compute
      `get_effective_survey_role(request.user, survey)` and require at least `viewer` via
      `SURVEY_ROLE_RANK`, following the inline pattern in
      `survey/access_control.py:13-16`.
- [x] 2.2 Raise `Http404` for every denial — anonymous, no role, wrong organization, and
      non-existent survey — so the responses are indistinguishable.
- [x] 2.3 Keep `@login_required` so anonymous callers redirect to login rather than reaching
      the role check; verify this does not turn the anonymous case into a distinguishable
      signal for a UUID that does not exist.
- [x] 2.4 Place the check before `_get_version_surveys` so the family expansion inherits the
      single decision made on the resolved survey.
- [x] 2.5 Log the denial server-side with the user id and survey uuid, so a support request
      can be told apart from a probe.

## 3. Tests

- [x] 3.1 `/surveys/` returns 301 to `/` and its body carries no survey name or UUID.
- [x] 3.2 A `private` survey and a `public`+`draft` survey appear on neither `/` nor
      `/surveys/`.
- [x] 3.3 `/sitemap.xml` has no bare `/surveys/` entry and still lists `/surveys/<uuid>/`.
- [x] 3.4 A user with `viewer` on the survey exports successfully (200, ZIP).
- [x] 3.5 A signed-in user from a second organization gets 404 and no export bytes — this is
      the test that fails against today's code; run it before the fix to confirm it does.
- [x] 3.6 An anonymous caller does not receive export data.
- [x] 3.7 A `SurveyCollaborator` on the canonical survey exports `?version=all` including
      archived version headers.
- [x] 3.8 Denial for an existing survey and for a random UUID produce the same status.
- [x] 3.9 A `private`+`published` survey without a password still opens by link for an
      anonymous visitor — the behaviour this change deliberately preserves.
- [x] 3.10 Docstrings in GIVEN/WHEN/THEN.

## 4. Verify

- [x] 4.1 `./run_tests.sh survey` green. Run `collectstatic` in this worktree first —
      `staticfiles/` is gitignored and its absence surfaces as unrelated template errors.
- [x] 4.2 `openspec validate tenant-data-exposure` passes.
- [ ] 4.3 Post-deploy, against production: `curl -sI https://mapsurvey.org/surveys/` is 301;
      `/sitemap.xml` has no bare `/surveys/`; a signed-in account with no role on a survey
      gets 404 from its `/download`.
