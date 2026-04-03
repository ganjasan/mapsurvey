## 1. Model and Migration

- [ ] 1.1 Add `TrackedLink` model to `survey/models.py` after `SurveyEvent`
- [ ] 1.2 Generate migration `0022_add_tracked_link.py`

## 2. UTM Capture

- [ ] 2.1 Add `extract_utm_params()`, `store_utm_in_session()`, `consume_utm_from_session()` to `survey/events.py`
- [ ] 2.2 Modify `build_session_start_metadata()` to consume UTM from session
- [ ] 2.3 Call `store_utm_in_session(request)` in `survey_header` before redirect
- [ ] 2.4 Call `store_utm_in_session(request)` in `survey_language_select` GET branch

## 3. Share Page

- [ ] 3.1 Create `survey/share_views.py` — `TrackedLinkForm`, `share_page` (GET+POST), `share_link_delete`
- [ ] 3.2 Add 2 URL patterns in `survey/urls.py`
- [ ] 3.3 Create `survey/templates/editor/survey_share.html` — form, link table, copy button, QR modal (qrcode.js CDN)

## 4. Campaign Analytics

- [ ] 4.1 Add `get_campaign_breakdown()` to `PerformanceAnalyticsService` in `survey/analytics.py`
- [ ] 4.2 Add `campaign_breakdown` to `analytics_dashboard` view context
- [ ] 4.3 Add Campaign Breakdown table to `analytics_performance.html`

## 5. Navigation

- [ ] 5.1 Add Share icon `<a>` to `survey_detail.html` navbar
- [ ] 5.2 Add Share icon `<a>` to `analytics_dashboard.html` navbar

## 6. Tests

- [ ] 6.1 `UtmCaptureTest` — store/consume params, params in session_start event, no UTM doesn't break
- [ ] 6.2 `TrackedLinkModelTest` — build_url with/without optional params
- [ ] 6.3 `ShareViewTest` — GET 200, POST creates link, missing source error, viewer 403
- [ ] 6.4 `CampaignAnalyticsTest` — groups by UTM triple, excludes non-UTM sessions
