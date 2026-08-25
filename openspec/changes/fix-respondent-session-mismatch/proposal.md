# Fix: a stale respondent session 500s every other survey on the site

## Why

`survey_session_id` is one site-wide cookie. `survey_section` trusts it blindly: it loads the
session, takes `session.survey` as the survey to serve, and does a bare
`SurveySection.objects.get(survey_header=session_survey, name=section_name)`
(`survey/views.py:902`). When the cookie points at a session from a **different** survey — the
respondent finished survey A and opened survey B by direct section link — the lookup asks for B's
section name inside A and raises `SurveySection.DoesNotExist`, an unhandled 500.

Only the survey *entry* view (`/surveys/<slug>/`) clears the cookie. Every direct section link
bypasses it — and direct section links are what actually circulate: the entry view itself redirects
respondents to them, so that is what gets copied out of the address bar and shared.

This is live: creator adorion@cabinworks.ca (user 390) wrote to support that Finish "doesn't
submit". Render logs show her IP getting dozens of POST → 500 on her second survey right after she
finished her first one (2026-08-24 23:12–23:15 UTC), and reproducing with a stale cookie against
her survey returns `Server Error (500)`. Her Crime Watch survey went out to a Facebook group; any
respondent who takes both of her surveys in one browser hits the same wall, silently.

## What Changes

- `survey_section` validates the cookie's session before using it: the session must exist, not be
  soft-deleted, and belong to the requested survey's family (the canonical header itself or one of
  its versions). Anything else starts a fresh session against the canonical survey, exactly as a
  first visit would.
- The section lookup stops being a bare `.get()`: if the (now correctly scoped) survey has no
  section by that name — a stale or mistyped link — the respondent is redirected to the survey
  entry point instead of a 500.
- Version routing is preserved: a valid session pinned to an archived version keeps serving that
  version's sections.

Not in scope: sharing one respondent session across surveys, or any change to how the thanks page
clears the session.
