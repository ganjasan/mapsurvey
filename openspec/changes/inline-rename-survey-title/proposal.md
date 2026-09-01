## Why

The survey name in the editor navbar is the most title-shaped thing on the page — bold,
1.1rem, first in the row after Dashboard — and it is a dead `<span>`. Creators click it
expecting to rename, and nothing happens; the owner reads this in the logs as repeated
clicks on `.survey-name` that produce no navigation and no request.

Renaming today lives one page away, in Survey settings, as a form field labelled `name`
with the placeholder `survey_name` (`survey/editor_forms.py:114`). Both the label and the
placeholder tell a creator this is an identifier they should not touch, which is why the
demo survey is called `demo_city_feedback`. It is not an identifier:
`SurveyHeader.name` is validated only by `RegexValidator(r'\w')` — "must contain at least
one letter or digit" — and every URL in the product is built from `uuid`. The field has
been free-form display text since the URL validator was relaxed; nothing in the product
tells the creator that.

So the fix is not a new field. It is putting the edit affordance where creators already
try to use it, and letting the name look like a title.

## What Changes

- **The navbar title becomes editable in place.** Click (or focus + Enter) turns the
  `.survey-name` span into an input seeded with the current name; Enter or blur saves,
  Escape restores the previous value. A single save endpoint writes `SurveyHeader.name`
  and nothing else.
- **One partial for all five headers.** `survey_detail`, `survey_settings`, `survey_share`,
  `analytics_dashboard` and `public_results` each hand-roll their own `<span class="survey-name">`.
  They move to `editor/partials/_survey_title.html`, so the affordance cannot be present on
  one editor page and missing on the next.
- **Permission follows Survey settings.** Renaming is owner-gated exactly like
  `editor_survey_settings` (`@survey_permission_required('owner')`). A non-owner sees the
  same plain text as today, with no edit affordance and no editable input in the markup.
- **The 45-character limit becomes visible.** The inline input carries `maxlength="45"` and
  shows a counter as the creator approaches it, and the server returns a field error rather
  than a silent truncation. This is the first half of
  `openspec/backlog/bug-survey-name-silently-truncated.md`; the same `maxlength` + counter
  goes onto the settings field so the two surfaces agree.
- **The settings field stops calling itself an identifier**: label and placeholder change
  from `name` / `survey_name` to a survey-title wording, and the field keeps working as the
  slower path to the same value.
- **Draft copies stay read-only.** A draft copy's header reads `Draft of <published name>`;
  that stays a plain span. Renaming happens on the canonical header, and a draft's rename
  reaches respondents through publication like every other draft edit. (Owner decision,
  2026-09-01.)

Not in scope:
- **Widening the column past 45 chars.** That is the second half of the truncation bug: it
  needs a migration plus a pass over how a 100-character name behaves in the navbar grid,
  the respondent header and the share preview. This change makes the limit honest; it does
  not move it. The backlog item stays open with option 1 struck out.
- Renaming from the dashboard survey cards, and any change to `SurveySection` or `Question`
  titles.

## Capabilities

### New Capabilities
- `survey-title-rename`: renaming a survey from the editor header — the affordance, the save
  endpoint, permission and length rules, and where the affordance is absent.

### Modified Capabilities
None. `SurveyHeader.name` semantics are unchanged; only where and how it is edited changes.
