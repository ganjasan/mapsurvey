# Design

## D1. Validate the session, don't clear the cookie preemptively

The alternative — clearing `survey_session_id` on every survey/section boundary crossing — would
also fix the 500, but it decides *when* a session ends in several places at once. Validating at the
point of use keeps a single rule: the cookie is a hint; `survey_section` only honours it when the
session it names is usable **for this survey**. A rejected hint degrades to the first-visit path
(new session + `session_start` event + `record_demo_open`), which already exists and is tested.

"Usable" means all of:
- the `SurveySession` row exists (the deleted-row branch already existed and folds into this);
- it is not soft-deleted (`is_deleted`) — continuing one would write answers into the trash;
- its survey is the requested canonical header or has `canonical_survey_id` pointing at it.

The family check (rather than strict `survey_id == survey.id`) is what preserves version routing:
a respondent who started before a new version was published keeps their archived-version session.

## D2. Section miss redirects to the entry point

With the session correctly scoped, a failed section lookup means a stale or hand-edited link. The
entry view (`survey_header`) already knows how to start over: it clears session state and redirects
to the head section. Redirecting there cannot loop — the head section's name always resolves.
`.filter(...).first()` replaces the bare `.get()`; a respondent URL must never 500 on data shape.

## D3. What stays as-is

`survey_thanks` and `survey_language_select` already guard their session lookups (`try/except`,
unconditional reset respectively). The analytics `section_view` emit below the fix reads the same
validated session id. POST re-reads the session by pk after validation — by then the id is
guaranteed fresh for this survey.
