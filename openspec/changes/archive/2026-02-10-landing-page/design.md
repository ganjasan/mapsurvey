## Context

The root URL (`/`) currently redirects to `/accounts/login/` for anonymous users and `/editor/` for authenticated users. There is no public-facing page. The project uses Django with Bootstrap 4, a simple `base.html` template with navbar/content/footer blocks, and PostGIS-backed models. There are no static CSS files — all styling comes from Bootstrap CDN.

The `SurveyHeader` model has no concept of visibility — all surveys are equal. There is no model for editorial content or stories.

The primary audience is architectural, urban planning, and urbanism firms. The landing page is a **sales tool** — the main conversion goal is to get visitors to contact us about ordering a survey, not self-service registration.

## Goals / Non-Goals

**Goals:**
- Public marketing landing page at `/` that converts visitors into leads
- Primary CTA: contact us to order a survey (email + Telegram)
- Showcase the platform to architectural, urban planning, and urbanism firms
- Display survey cards (demo, active, completed) as portfolio/proof of work
- Provide a stories/publications section for editorial content with maps and open data
- Distinctive visual identity appropriate for the architecture/urbanism domain
- Keep authenticated user flows (editor, login) intact

**Non-Goals:**
- Self-service registration or onboarding flow
- CMS or rich text editor for stories (admin-only for now)
- Real-time analytics dashboards
- Visual redesign of the existing survey/editor pages (they keep Bootstrap 4)
- i18n of the landing page itself (follow-up)

## Decisions

### 1. Primary CTA — Contact, not Registration

The hero's main button is **"Order a Survey"** / **"Заказать опрос"** which scrolls to a contact section. The contact section provides two channels:
- **Email**: `mailto:` link with a pre-filled subject line
- **Telegram**: `t.me/` direct link

Login/registration is completely absent from the landing page. Existing clients access `/accounts/login/` directly by URL.

**Why**: The business model is B2B service — clients don't create surveys themselves. The landing page should generate leads, not registrations.

### 2. Page structure — sales funnel flow

Sections in order:
1. **Hero** — headline, value proposition, primary CTA ("Order a Survey")
2. **How it works** — 3 steps: "Describe your task → We create a geo-survey → You get data and maps"
3. **Survey cards** — portfolio of demo/active/archived surveys (proof of capability)
4. **Stories** — published results, maps, open data (proof of value)
5. **Contact section** — email + Telegram with a clear call to action
6. **Footer** — navigation links, copyright

**Why**: Classic sales funnel — hook (hero) → explain (how it works) → prove (surveys + stories) → convert (contact).

### 3. Survey visibility flags on SurveyHeader

Add fields to `SurveyHeader`:
- `visibility`: CharField with choices `"private"` (default), `"demo"`, `"public"` — controls whether a survey appears on the landing page and in which section
- `is_archived`: BooleanField — marks completed surveys whose results can be shown

**Why**: Simplest approach. A single field controls display logic. The `"private"` default ensures existing surveys remain hidden from the landing page. `is_archived` separates "done, show results" from "still collecting."

### 4. Story model for publications

New `Story` model with:
- `title`, `slug`, `body` (TextField with HTML)
- `cover_image` (ImageField, optional)
- `story_type`: choices — `"map"`, `"open-data"`, `"results"`, `"article"`
- `survey` (FK to SurveyHeader, nullable — not all stories are survey-bound)
- `is_published` (BooleanField)
- `published_date` (DateTimeField)

**Why**: Stories are a distinct content type with their own lifecycle. A dedicated model keeps the data clean and lets admin manage them independently.

### 5. Separate base template — `base_landing.html`

Create `base_landing.html` as an **independent** base template, not extending `base.html`. The landing page needs:
- Its own `<head>` with viewport meta, Google Fonts, and `landing.css`
- Full-width sections without a `.container` wrapper
- Custom navbar with transparent-on-hero behavior
- Proper footer

The existing `base.html` stays untouched for editor/survey pages.

**Why**: The current `base.html` is a utilitarian scaffold for form-heavy pages. A marketing page has completely different layout needs. Clean separation is simpler.

### 6. Visual direction — Cartographic Editorial

The aesthetic targets the architecture/urbanism audience: precise, restrained, domain-specific.

- **Typography**: Geometric display font (Outfit or DM Sans) for headlines. Refined serif (Source Serif 4 or Literata) for body text. Google Fonts.
- **Color palette**: Warm off-white background (`#F5F2ED`), dark charcoal text (`#1A1A1A`), accent of surveyor's orange (`#E85D26`) or cadastral teal (`#2A7F6F`).
- **Layout**: Full-bleed hero with subtle topographic line pattern. Generous whitespace. Cards with 2px borders, no shadows.
- **Motion**: Minimal — staggered card reveals on scroll via CSS `animation-delay`.
- **No Bootstrap**: Custom CSS with CSS Grid and Flexbox.

### 7. View logic — replace the redirect

Change `index` view to:
- Query `SurveyHeader` filtered by `visibility__in=["demo", "public"]`, split into active and archived
- Query `Story.objects.filter(is_published=True)` ordered by `-published_date`
- Render `landing.html` with survey and story querysets
- Authenticated users see the same page but with "Editor" and "Logout" links in the navbar

### 8. Story detail page

Add `path('stories/<slug:slug>/', views.story_detail, name='story_detail')` for individual story pages. The detail template extends `base_landing.html`.

### 9. Contact settings

Store contact email and Telegram handle in `django.conf.settings` (`CONTACT_EMAIL`, `CONTACT_TELEGRAM`). The template reads them from context. This avoids hardcoding and allows easy changes.

### 10. No new frontend framework

Django templates + custom CSS. Vanilla JS only for scroll-to-contact, scroll-triggered animations, and mobile nav toggle.

## Risks / Trade-offs

- **Two base templates**: `base.html` and `base_landing.html` means duplicated navbar logic for auth state. → Acceptable; the navbars are visually different anyway.
- **Migration for existing surveys**: Adding `visibility` with default `"private"` is safe — no existing survey appears until explicitly changed in admin.
- **Story body format**: Raw HTML in TextField with `|safe` filter. → Mitigate by limiting story editing to admin users only.
- **Landing page replaces login redirect**: → Existing clients can access `/accounts/login/` directly. No login link on the landing page.
- **Google Fonts dependency**: → Use `font-display: swap` to avoid FOIT.
