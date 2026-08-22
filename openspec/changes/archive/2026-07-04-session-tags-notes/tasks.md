## 1. Model

- [ ] 1.1 Add `tags` JSONField (default=list, blank=True) to SurveySession
- [ ] 1.2 Add `notes` TextField (default='', blank=True) to SurveySession
- [ ] 1.3 Create migration 0025
- [ ] 1.4 Add tags/notes to serialization export

## 2. Endpoints

- [ ] 2.1 Add `analytics_session_update_tags` POST endpoint: accepts JSON `{tags: [...], notes: "..."}`
- [ ] 2.2 Add URL pattern

## 3. Table Integration

- [ ] 3.1 Add "Tags" system column in `get_table_page()` after Issues
- [ ] 3.2 Add `tags` and `notes` to row dicts
- [ ] 3.3 Render tags as badges in table cells
- [ ] 3.4 Tags column searchable via existing col_search

## 4. Session Detail Modal

- [ ] 4.1 Add tags/notes section in `analytics_session_detail.html`
- [ ] 4.2 Add tag input (comma-separated) + save button via HTMX/fetch
- [ ] 4.3 Add notes textarea + save button

## 5. Tests

- [ ] 5.1 Test tags/notes field defaults
- [ ] 5.2 Test update tags endpoint
- [ ] 5.3 Test tags appear in table
- [ ] 5.4 Test tags searchable in column search
