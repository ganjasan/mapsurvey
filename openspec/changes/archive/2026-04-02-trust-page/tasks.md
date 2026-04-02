## 1. View & URL

- [x] 1.1 Add `trust_page` FBV to `survey/views.py` with `@lang_override('en')` decorator, rendering `trust.html`
- [x] 1.2 Add URL pattern `path('trust/', views.trust_page, name='trust_page')` to `survey/urls.py`

## 2. Template

- [x] 2.1 Create `survey/templates/trust.html` extending `base_landing.html`
- [x] 2.2 Add hero section with title and subtitle
- [x] 2.3 Add "Data Privacy (GDPR)" section — anonymous respondents, no tracking, no IP storage, no cookies
- [x] 2.4 Add "Hosting & Data Residency" section — EU (Frankfurt), Render, SOC 2
- [x] 2.5 Add "Open Source & Transparency" section — GitHub link, AGPLv3, auditable
- [x] 2.6 Add "Security" section — HTTPS, Django defaults, no third-party trackers
- [x] 2.7 Add "Data Ownership" section — creators own data, export anytime, delete = gone
- [x] 2.8 Add "Who is behind Mapsurvey" section — Artem Konuchov, independent, open-source
- [x] 2.9 Add DPA download CTA section with link to static PDF

## 3. DPA Document

- [x] 3.1 Generate DPA template PDF with Mapsurvey-specific details and place in `staticfiles/docs/mapsurvey-dpa.pdf`

## 4. CSS

- [x] 4.1 Add trust page styles to `staticfiles/css/landing.css` (section layout, typography, DPA download button)

## 5. Navigation

- [x] 5.1 Add "Trust" link to nav bar in `base_landing.html` (between Demo and GitHub)
- [x] 5.2 Add "Trust" / "Legal" column to footer in `base_landing.html` with Trust page link

## 6. SEO

- [x] 6.1 Add `/trust/` to `sitemap_xml` view in `survey/views.py`
