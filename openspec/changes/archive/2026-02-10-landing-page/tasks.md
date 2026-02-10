## 1. Models & Migrations

- [x] 1.1 Add `visibility` CharField (choices: private/demo/public, default "private") and `is_archived` BooleanField (default False) to `SurveyHeader` model
- [x] 1.2 Create `Story` model with title, slug, body, cover_image, story_type, survey FK, is_published, published_date
- [x] 1.3 Generate and apply migration for SurveyHeader fields and Story model
- [x] 1.4 Register Story model in Django admin with list_display: title, story_type, is_published, published_date

## 2. Configuration

- [x] 2.1 Add `CONTACT_EMAIL` and `CONTACT_TELEGRAM` settings to Django settings and pass them to landing template context

## 3. Base Template & Static Assets

- [x] 3.1 Create `survey/static/survey/landing.css` with CSS variables, typography (Google Fonts: display + serif), color palette, and reset styles
- [x] 3.2 Create `base_landing.html` template with: viewport meta, Google Fonts link, landing.css, navbar block, content block, footer block
- [x] 3.3 Implement landing navbar in `base_landing.html` with section anchor links (Surveys, Stories, Contact) and for authenticated users: Editor + Logout. No login/registration links.
- [x] 3.4 Implement landing footer in `base_landing.html` with contact info (email + Telegram), navigation links, and copyright

## 4. Landing Page View & Template

- [x] 4.1 Rewrite `index` view to query visible surveys (with session counts) and published stories, render `landing.html`
- [x] 4.2 Create `landing.html` extending `base_landing.html` with hero section (headline, description, primary CTA "Order a Survey" scrolling to contact, secondary CTA "Browse Surveys" scrolling to surveys)
- [x] 4.3 Add "How it works" section: 3 steps — describe task, we create survey, you get data
- [x] 4.4 Add survey cards section — cards with name, organization, status badge, response count, ordered by demo/active/archived; hidden if no visible surveys
- [x] 4.5 Add stories section — cards with title, type badge, cover image or placeholder, published date; hidden if no published stories
- [x] 4.6 Add contact section with email (mailto:) and Telegram (t.me/) links from settings

## 5. Landing Page Styles

- [x] 5.1 Style hero section: full-bleed layout, topographic background pattern, headline/body typography, primary + secondary CTA buttons
- [x] 5.2 Style how-it-works section: 3-column layout with step numbers, responsive
- [x] 5.3 Style survey cards: CSS Grid layout, 2px border cards, status badges (demo/active/archived colors), responsive
- [x] 5.4 Style story cards: cover image or placeholder background, type badge, responsive grid
- [x] 5.5 Style contact section: prominent email + Telegram buttons/links
- [x] 5.6 Style navbar: landing-specific look, mobile nav toggle with vanilla JS
- [x] 5.7 Style footer: muted palette, contact + link layout
- [x] 5.8 Add scroll-triggered card reveal animations with CSS animation-delay
- [x] 5.9 Add smooth scroll behavior for anchor links (hero CTA → contact, navbar → sections)

## 6. Story Detail Page

- [x] 6.1 Add `story_detail` view: query published Story by slug (404 for unpublished/missing)
- [x] 6.2 Add URL pattern `stories/<slug:slug>/` in survey/urls.py
- [x] 6.3 Create `story_detail.html` extending `base_landing.html` with title, date, type, body, cover image, and optional survey link

## 7. Tests

- [x] 7.1 Test SurveyHeader visibility/is_archived field defaults and choices
- [x] 7.2 Test Story model creation, slug uniqueness, nullable survey FK
- [x] 7.3 Test index view returns landing page (no redirect) for anonymous and authenticated users
- [x] 7.4 Test index view only includes surveys with visibility demo/public, correct ordering
- [x] 7.5 Test index view hides sections when no visible surveys / no published stories
- [x] 7.6 Test story_detail view returns 200 for published story, 404 for unpublished and non-existent
- [x] 7.7 Test story_detail view includes survey link when story has survey FK
