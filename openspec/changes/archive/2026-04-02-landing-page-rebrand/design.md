## Technical Approach

Keep the existing Django template architecture (Variant A): `base_landing.html` → `landing.html`, custom CSS, no SPA. Use the `frontend-design` skill for the actual visual design — it will handle creative direction, color palette, typography, and high-quality CSS.

### Files to Modify

**Templates:**
- `survey/templates/base_landing.html` — rebuild navbar (product nav: Features, Demo, Pricing, Docs, GitHub; auth-aware; mobile hamburger) and footer (product links, social links, language switcher, license notice). Add SEO blocks. Add `extra_js` block.
- `survey/templates/landing.html` — complete rewrite: hero, problem-solution, features, demo, comparison, use-cases, tech-stack + quick-start, social proof, pricing sections. Remove: how-it-works, survey-cards, stories, contact.

**Views:**
- `survey/views.py` `index()` — remove survey/story querysets, add `GITHUB_REPO_URL` and `DEMO_SURVEY_URL` to context

**Settings:**
- `mapsurvey/settings.py` — add `GITHUB_REPO_URL` and `DEMO_SURVEY_URL` settings

**Context processors:**
- `survey/context_processors.py` — add `github` context processor for `GITHUB_REPO_URL`

**Static:**
- `survey/assets/css/landing.css` — complete rewrite via `frontend-design` skill

### Architecture Decisions

1. **CSS approach**: vanilla CSS (no Tailwind) — matches existing pattern, zero build step. The `frontend-design` skill will generate distinctive, production-grade CSS with CSS custom properties, responsive grid, and dark mode via `prefers-color-scheme`.

2. **i18n approach**: Use Django `{% trans %}` / `{% blocktrans %}` tags for all user-visible text. Generate `.po` entries for EN and RU. The comparison table data can be inline in the template with `{% trans %}` per cell.

3. **Dark mode**: CSS-only via `prefers-color-scheme: dark` media query in landing.css — no JS toggle needed for v1.

4. **Demo section**: Conditional iframe via `DEMO_SURVEY_URL` setting. Fallback: hide section or show placeholder text. No video/GIF asset for v1.

5. **GitHub stars badge**: Use shields.io `img` tag — no API call needed, CDN-cached.

6. **Schema.org JSON-LD**: Inline `<script type="application/ld+json">` in `base_landing.html` head, populated from template context.

7. **Scroll animations**: Keep existing IntersectionObserver pattern (`.reveal` / `.is-visible`).

8. **Fonts**: Switch from Outfit + Source Serif 4 to a more distinctive combination. Let `frontend-design` choose — candidates: DM Sans / Inter / Satoshi for headings, system serif or Source Serif for body, JetBrains Mono for code blocks.
