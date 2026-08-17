## Context

Two public surfaces in the `/surveys/` namespace were never given an authorization model.

`survey_list` (`survey/views.py:555`) predates organizations, roles, and `visibility`
entirely — it is four lines that render `SurveyHeader.objects.filter(deleted_at__isnull=True)`
through a template with no markup. It was almost certainly a development aid that survived
into production. Its sibling `index` (`survey/views.py:441`) was later given the correct
filters; `survey_list` never was.

`download_data` (`survey/views.py:1027`) carries `@login_required`. The structure export
next to it, `export_survey` (`survey/views.py:1315`), carries
`@survey_permission_required('viewer')`. The response export is the one that was missed,
and it is the one that returns respondent data.

The constraint that shapes both fixes: `visibility='private'` is a *discovery* setting, not
an access control. A private published survey is meant to open for anyone holding the link
— that is how a creator runs a closed survey with their own audience. Access to answer a
survey is therefore link-based by design, and only the *listing* violated it. Access to
export answers is role-based and always should have been.

Every real link to `download_data` comes from the editor UI
(`survey/templates/editor/_survey_more_menu.html`, `analytics_dashboard.html`) and always
interpolates `{{ survey.uuid }}`.

## Goals / Non-Goals

**Goals:**
- No unauthenticated surface enumerates surveys across organizations.
- Exporting responses requires a role on that survey, matching `export_survey`.
- Denial on a public-namespace URL does not disclose whether a survey exists.
- The dual-lookup contract for `/surveys/<survey_slug>/...` in `uuid-survey-identification`
  stays intact.

**Non-Goals:**
- Changing `check_survey_access`. Link-based access to an unlisted survey is intended.
- Moving `download_data` under `/editor/`. Creators have the current URL in bookmarks and
  scripts; relocating it is a separate, breaking change.
- Reworking `visibility` semantics or the `SurveyCollaborator` model.
- The sitemap advertising drafts, and `Http404` reaching PostHog error tracking. Same
  investigation, separate change.

## Decisions

**Remove the listing rather than filter it.**
Filtering `survey_list` down to `visibility in (public, demo)` and `status='published'`
would duplicate `index`, which already renders exactly that set with cards and copy. Two
implementations of one query is how this defect arose — `index` was fixed, `survey_list`
was forgotten. Deleting the view, the route, and `survey_list.html` leaves one
implementation. Verified nothing depends on it: no `reverse('survey_list')`, no
`{% url %}`, no `href`, no test issues a request to it. The only artifact referencing the
page is a spec scenario, which this change removes with it.

**301 to `/`, not 404 or 410.**
The URL sat in `sitemap.xml` and is allowed in `robots.txt`, so it may be indexed. A 410
would be the honest "this is gone" signal, but the landing page is a genuine successor —
it lists the public surveys this page was trying to list. 301 keeps any accumulated link
equity and sends a human who bookmarked it somewhere useful. Rejected 404 outright: it
loses both.

**Authorize inside `download_data`, not via `survey_permission_required`.**
The decorator looks up `SurveyHeader.objects.get(uuid=kwargs[survey_kwarg])`. Handing it
`survey_slug` would break the dual lookup that `uuid-survey-identification` requires for
`/surveys/<survey_slug>/...`, and a non-UUID slug would raise inside the ORM rather than
resolve to a name. So: keep `resolve_survey`, then check the role on the resolved survey
with the same helpers the decorator uses (`get_effective_survey_role`, compared against
`SURVEY_ROLE_RANK`). `check_survey_access` already establishes this inline pattern.
Alternative considered — teach the decorator to accept a resolver callable — is cleaner in
the abstract but edits a decorator that guards ~25 editor views, for the benefit of one
view outside that family. Rejected on blast radius.

**Minimum role `viewer`.**
Matches `export_survey` and the analytics views (`analytics_views.py:83`), which already
expose the same answers through the dashboard. Requiring `editor` would mean a viewer can
read every response on screen but not save them to disk, which is a distinction without a
security difference.

**Denial returns 404, uniformly.**
The decorator distinguishes 403 (insufficient role) from 404 (wrong org), which is right
for `/editor/` routes where the caller is already known to belong. On a public-namespace
URL, a 403 confirms that a UUID names a real survey, which is precisely the fact the
removed listing used to leak. Non-existent, wrong-org, and no-role therefore all return
404.

**Check the role once, on the resolved survey, before expanding versions.**
`download_data` calls `_get_version_surveys`, which for `?version=all` returns the whole
canonical family. Re-checking each archived header would deny an explicit
`SurveyCollaborator` who holds a role on the canonical survey but has no collaborator row
on the archived version headers — `get_effective_survey_role` is per-survey and only the
org baseline carries across the family. Authorize the survey the URL names; the family is
that survey's own history.

## Risks / Trade-offs

- **A creator's script calls `/surveys/<uuid>/download` with session auth** → Unaffected as
  long as the account holds a role on that survey. Only cross-tenant callers break, which
  is the change.
- **Uniform 404 makes a genuine permission problem look like a missing survey** → Accepted.
  The editor UI only renders the link for surveys the user can already see, so a creator
  meeting this 404 is off the happy path. Log the denial server-side so support can tell
  the two apart.
- **`301 → /` on an indexed URL is not reversible in search results quickly** → Low impact;
  the destination is a real page and the redirect can be changed later.
- **Removing the route while an unknown external integration polls it** → No evidence of
  such traffic, but the Render log filter for the exact path proved unreliable (a control
  query on `/sitemap.xml` returned known requests, the same query shape on `/surveys/`
  returned none despite requests existing). A 100-request sample of `/surveys/*` over ~33
  hours contained zero hits on the listing. Treat as indicative, not proven; the 301
  covers the case anyway.
- **The fix is invisible in tests unless they assert denial** → Tests must cover a second
  organization attempting the export, not only the owner succeeding. A happy-path-only test
  passes just as well against the vulnerable code.

## Migration Plan

No database migration. Deploy order does not matter — the two fixes are independent.

Post-deploy verification, in production:
1. `curl -sI https://mapsurvey.org/surveys/` returns 301 to `/`.
2. `/sitemap.xml` no longer contains a bare `/surveys/` entry, and still contains
   `/surveys/<uuid>/` entries.
3. A signed-in account with no role on a survey receives 404 from
   `/surveys/<that-uuid>/download`.

Rollback is a revert; nothing persists state.

## Open Questions

- Should the denial be logged as an `AbuseEvent`, or is a plain server log enough? An
  authenticated cross-tenant export attempt is a stronger signal than most of what
  `AbuseEvent` currently records.
- Do any of the 166 organizations rely on `/surveys/` as an informal index? Nothing in the
  code or the sampled logs suggests it, and no support request is known, but the question
  is answered by shipping the 301 rather than a 404.
