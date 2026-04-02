## Context

The project has no trust, security, or privacy page. Public-facing informational pages follow the landing page pattern: FBV with `@lang_override('en')`, template extending `base_landing.html`, custom CSS in `landing.css`. The landing page nav and footer are defined in `base_landing.html` and shared across all pages using that base.

## Goals / Non-Goals

**Goals:**
- Create a professional trust page that satisfies IT security team reviews
- Provide a downloadable DPA template
- Integrate into existing landing page navigation

**Non-Goals:**
- i18n / translations (deferred until site-wide translation effort)
- Auto-generated PDF version of the trust page
- Interactive compliance questionnaire or self-assessment tool
- Cookie consent banner (no cookies used for tracking)

## Decisions

### 1. Simple FBV + template (not a CMS model)

The trust page has static content that changes infrequently. A `TrustPage` model or CMS-like approach would add unnecessary complexity. A plain template with hardcoded content matches the landing page pattern and is easy to update directly in code.

**Alternative considered**: Store content in a model editable via admin. Rejected — overkill for a single static page, and content changes require careful review anyway.

### 2. DPA as static PDF (not generated)

A pre-made PDF in `staticfiles/docs/` served via Django's static files. IT teams expect a signable document format, not a web page.

**Alternative considered**: HTML page with print CSS. Rejected — institutional workflows expect PDF/DOCX attachments they can circulate and sign.

### 3. CSS within landing.css (not a separate file)

The trust page uses the same design system as the landing page. Adding trust-page-specific styles to `landing.css` keeps things in one place and avoids an extra HTTP request.

## Components

### View: `trust_page` in `survey/views.py`
- Decorated with `@lang_override('en')`
- Renders `trust.html`
- No model queries needed

### Template: `survey/templates/trust.html`
- Extends `base_landing.html`
- Sections: hero, data privacy, hosting, open source, security, data ownership, about, DPA download CTA
- Links to DPA PDF via `{% static 'docs/mapsurvey-dpa.pdf' %}`

### Static file: `staticfiles/docs/mapsurvey-dpa.pdf`
- Standard DPA template with Mapsurvey-specific details pre-filled
- Covers: parties, scope, data types, processing purposes, sub-processors, security measures, data subject rights, breach notification, term and termination

### URL: `path('trust/', views.trust_page, name='trust_page')`
- Added to `survey/urls.py`

### Navigation: `base_landing.html`
- "Trust" link added to nav bar (between Demo and GitHub)
- "Trust" link added to footer under a "Legal" or "Trust" column
