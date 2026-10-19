## Context

`views.editor` already batches the "started" count (`family_counts`, grouped by
`Coalesce(survey__canonical_survey_id, survey_id)`), drafts, files and comments. The two
remaining card numbers came from `SurveyAnalyticsService(survey).get_overview()` per survey,
which resolves the version scope, walks every version's sections, counts, and then runs
`compute_session_issues()` for a `flagged_count` the dashboard discards.

## Decisions

**One helper next to the definition, not in the view.** `family_completion_counts(surveys)` lives
in `analytics.py` beside `completed_session_filter`, and applies that function's rule to many
families at once: a session is completed when it has an answer to a question in the last
section of its own version. Sections belong to one version, so filtering by the union of every
version's last section is the same as filtering each version by its own — which is exactly what
`completed_session_filter` already does over a family scope.

**Queries, independent of the number of surveys:**
1. headers of the families: `SurveyHeader` with `id IN ids OR canonical_survey_id IN ids` →
   `(id, family)`. Draft copies link through `published_version`, not `canonical_survey`, so
   they are excluded the same way `family_ids()` excludes them.
2. their sections: one `SurveySection` query, ordered per header in Python with the same
   linked-list walk `_get_ordered_sections` uses (split out as `_order_sections`).
3. totals: active sessions of those headers, grouped by family.
4. completed: the same, restricted to answers in the last sections, `Count('id', distinct=True)`
   grouped by family.

**Rate stays computed as before**: `round(completed / total * 100)` when `total > 0`, else 0.

**`get_overview()` is not changed.** The Responses page needs `flagged_count`; making the
dashboard cheap does not require touching it. The equivalence test pins the two to the same
numbers.

## Risks

- "Started" on the card is `family_counts`, which includes deleted sessions, while the rate is
  over non-deleted ones. That mismatch predates this change and is kept on purpose — this
  change must not move any number creators see.
