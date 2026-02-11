## Why

Users have no way to tell how long a survey is when navigating page by page. Without understanding progress, respondents may abandon a survey mid-way thinking it's too long. A simple "3/7" counter would set expectations and reduce drop-off.

## What Changes

- Add a progress indicator (e.g., "3 / 7") to the survey section page, showing current section number and total section count
- Compute current section index and total sections in the `survey_section` view and pass to the template
- Display the indicator in the survey section template header area, visible on both mobile and desktop layouts

## Capabilities

### New Capabilities
- `survey-progress`: Progress indicator displaying current section position out of total sections during survey completion

### Modified Capabilities

_(none — this is purely additive UI, no existing spec-level behavior changes)_

## Impact

- **View**: `survey/views.py` — `survey_section()` needs to compute section index and total count by traversing the linked-list of sections (via `next_section`/`prev_section`), then pass them to the template context
- **Template**: `survey/templates/survey_section.html` or `base_survey_template.html` — render the progress indicator in the header area
- **CSS**: `survey/static/css/main.css` — minimal styling for the progress indicator
- **No model changes** — sections already have `next_section`/`prev_section` links; no new fields needed
- **No migration needed**
