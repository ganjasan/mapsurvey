# `SurveySession.end_datetime` is never written (0 of 4586 rows)

**Type**: bug
**Priority**: high
**Area**: backend
**Created**: 2026-08-05

## Description

`survey_surveysession.end_datetime` is null for **every session in production**:

```sql
SELECT count(*) AS total, count(end_datetime) AS with_end
  FROM survey_surveysession WHERE is_deleted = false;
-- total 4586 | with_end 0
```

The column exists, is nullable, and nothing ever sets it. Every session in the database looks
identical to an abandoned one.

## Why it matters

We cannot tell a finished response from a dropped one. That blocks, at minimum:

- completion rate, per survey and per version, which is the first question any author asks
  about a long survey;
- time-on-survey, the obvious follow-up ("is my 106-question survey too long?");
- honest response counts in the funnel and in the editor dashboard, where a session opened and
  abandoned in five seconds currently weighs the same as a completed one.

It also quietly distorts outreach: an account showing "22 responses" may be one person opening
the survey 22 times, which is exactly what happened with the Ansouis ZAP account on
2026-08-04.

## Where the fix belongs

The thanks page is the natural completion signal: reaching `/surveys/<name>/thanks/` is what
"finished" means today. Setting `end_datetime` there covers the honest path without inventing
a new concept.

Worth deciding explicitly: whether submitting the last section counts as completion even if
the respondent never lands on the thanks page, and what a session with no last section
(single-section surveys) should record.

## Backfill

Not possible retroactively in any honest way. Historical sessions stay null; any completion
metric has to start from the deploy date and say so, the same way the `DemoOpen` split does.

## Notes

- Found during the production review of the Ansouis ZAP account on 2026-08-05, incidentally.
  Not user-reported.
- Related: [Export filter: completed surveys only](feature-export-completed-only-filter.md) —
  that filter cannot be built at all until this field is populated.
- **Priority raised medium → high 2026-08-21**: this is the missing half of the
  creator-facing completion funnel. `PerformanceAnalyticsService` already renders the
  section funnel on Results → Performance, but "opened → finished" cannot be shown until
  completion is recorded — and that funnel is the collection-side counterpart of the
  distribution work ([Launch kit](feature-publish-launch-kit.md) #132,
  [Embed widget](feature-survey-embed-widget.md) #131): once creators drive real traffic,
  "where do respondents give up" is the first question they will ask.
