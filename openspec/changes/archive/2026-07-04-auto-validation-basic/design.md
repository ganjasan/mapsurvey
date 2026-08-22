## Context

`SurveyAnalyticsService` already computes completion via `get_overview()` (sessions with answers in last section). The attribute table has system columns (id, validation_status, start_datetime, language). The three basic rules require comparing Answer rows against survey structure.

`Question.required` is only enforced client-side (HTML form validation). Server-side `survey_section` POST handler saves whatever `request.POST` provides without calling `form.is_valid()`. So missing required answers = no Answer row exists for that question+session.

## Goals / Non-Goals

**Goals:**
- Compute 3 issue types per session: empty, incomplete, missing_required
- Display as "Issues" system column with badges
- Dropdown filter by issue type
- Flagged count in overview
- All computation on-the-fly (no stored state)

**Non-Goals:**
- Auto-setting validation_status
- Advanced rules (fast completion, geo outliers, duplicates) — deferred to #49
- Per-answer linting — deferred to #44

## Decisions

### 1. `compute_session_issues()` returns dict of lists

`{session_id: ['empty', 'incomplete', 'missing_required']}` — a session can have multiple issues (e.g., incomplete AND missing required in sections it did visit). Empty sessions are also always incomplete, but we flag both for clarity.

### 2. Three bulk queries for efficiency

1. **Answer count per session**: `Answer.objects.filter(session_id__in=pks, parent_answer_id__isnull=True).values('survey_session_id').annotate(cnt=Count('id'))` — sessions with cnt=0 are "empty"
2. **Completed session IDs**: `base_qs.filter(answer__question__survey_section=last_section).distinct()` — sessions NOT in this set are "incomplete"
3. **Required question coverage**: `Answer.objects.filter(session_id__in=pks, question__required=True, parent_answer_id__isnull=True).values_list('survey_session_id', 'question_id')` — compare against `Question.objects.filter(required=True, survey_section__survey_header=survey)` per section

### 3. Issues column position: after validation_status (3rd system column)

System columns: #ID, Status, Issues, Start time, Language — then question columns.

### 4. Issues filter as query param `?issues=empty` / `?issues=incomplete` / `?issues=missing_required`

The filter is applied in Python after `compute_session_issues()` runs, before pagination. Similar to `col_search` handling.
