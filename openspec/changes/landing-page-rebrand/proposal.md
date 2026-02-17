## Why

The current landing page (`/`) positions Mapsurvey as a service — "Order a Survey" for architecture and urban planning firms. The project is pivoting to an **open-source PPGIS platform** (the "open-source alternative to Maptionnaire") with two acquisition channels: a free cloud tier at mapsurvey.org and self-hosting via Docker. The landing page must communicate this new positioning, drive sign-ups and GitHub stars, and capture SEO clusters currently unoccupied: "open source PPGIS," "self-hosted participatory mapping," "free map survey tool," "Maptionnaire alternative."

The current hero CTA ("Order a Survey" → contact section) and service-oriented "How it works" flow are wrong for a product with open registration. The page needs to lead with self-serve CTAs ("Try Free" / "Self-Host"), showcase interactive map survey features, and build trust with developers and researchers who evaluate tools by code, architecture, and data control.

## What Changes

- **Replace hero section** — new H1 "Open-source platform for participatory mapping," dual CTA (Try Free → sign up, Self-Host → GitHub), trust badges (Open Source, Free to Start, Self-Hostable, GDPR-Friendly), product screenshot or interactive demo
- **Replace "How it works" with Problem → Solution section** — before/after comparison: cost ($1,400+/project → free), data control (vendor → self-hosted), geometry (pin-only → points/lines/polygons), data export (locked → GeoJSON/CSV), code (closed → open-source)
- **Add Features section** — 6 cards: Interactive map surveys, 13 question types, Multilingual surveys, Data export, Deploy in minutes, Open source
- **Add Interactive Demo section** — embedded iframe with a live demo survey or fallback video/GIF
- **Add Comparison Table section** — Mapsurvey vs Maptionnaire vs KoBoToolbox vs ArcGIS Survey123 across 10 dimensions (open source, self-host, cost, geometry types, public-facing, export, visual editor, data control)
- **Add Use Cases section** — 4 cards: Urban Planning, Academic Research, Civic Tech / NGOs, Municipalities
- **Add Tech Architecture section** — stack diagram (Django + GeoDjango + PostGIS + HTMX + Leaflet), key points for developers, "View on GitHub" CTA
- **Add Quick Start section** — 3-command self-host deployment (git clone, docker compose up, open localhost:8000)
- **Add Social Proof section** — GitHub stars badge, "Built with Django & PostGIS" trust signal, ITMO University provenance
- **Replace Pricing section** — 3 columns: Free (cloud, limited), Pro (coming soon), Self-Hosted (free forever, unlimited)
- **Rebuild Footer** — product navigation, documentation links, social links (GitHub, Mastodon, Twitter/X), language switcher (EN/RU), open-source license notice
- **Rebuild Navbar** — product navigation (Features, Demo, Pricing, Docs, GitHub), Sign In button, mobile hamburger menu
- **Add SEO meta tags** — title, description, keywords, Open Graph, Twitter Card, Schema.org SoftwareApplication structured data
- **Remove** — "Order a Survey" CTA, "How it works" 3-step service flow, Telegram/email contact section, survey cards section, stories section (deferred to /blog)

## Capabilities

### New Capabilities
- `landing-hero-v2`: Hero section with product positioning headline, dual CTA buttons (Try Free / Self-Host), trust badges, product screenshot/demo visual
- `landing-problem-solution`: Before/after comparison section contrasting status quo with Mapsurvey value propositions
- `landing-features`: 6 feature cards with icons and expandable descriptions
- `landing-demo`: Embedded interactive demo survey (iframe) or fallback video
- `landing-comparison`: Feature comparison table vs Maptionnaire, KoBoToolbox, ArcGIS Survey123
- `landing-use-cases`: 4 audience-specific use case cards (urban planning, research, civic tech, municipalities)
- `landing-tech-stack`: Architecture diagram and developer-focused section with GitHub CTA
- `landing-quick-start`: 3-command self-host deployment code block
- `landing-social-proof`: Trust signals — GitHub stars, tech provenance, institutional origin
- `landing-pricing`: 3-tier pricing table (Free / Pro / Self-Hosted)
- `landing-seo`: Meta tags (title, description, OG, Twitter Card), Schema.org structured data, hreflang for EN/RU

### Modified Capabilities
- `landing-page`: Complete overhaul — new positioning, new sections, new CTAs, new visual identity. Retains: separate `base_landing.html`, custom CSS (no Bootstrap), full-width sections, auth-aware navbar
- `survey-cards`: Removed from landing page (moved to /editor/ dashboard only)
- `public-stories`: Removed from landing page (deferred to future /blog route)

## Impact

- **Templates**: Complete rewrite of `landing.html`; update `base_landing.html` navbar and footer; remove stories and survey-cards sections from landing context
- **Views**: `index` view in `survey/views.py` — remove survey/story querysets, add SEO context (meta tags, structured data)
- **Static assets**: Major `landing.css` rewrite; new section styles (hero, features grid, comparison table, pricing cards, code blocks); add product screenshots; possibly add Tailwind CSS or keep vanilla CSS
- **URLs**: No route changes — `/` still serves landing. Stories route `/stories/<slug>/` may be removed or kept dormant
- **Settings**: Add `GITHUB_REPO_URL`, remove or keep `CONTACT_EMAIL`/`CONTACT_TELEGRAM` (contact section removed from landing but may be used elsewhere)
- **SEO**: New `<head>` block with meta tags, OG tags, Schema.org JSON-LD script
- **i18n**: Content must support EN (primary) and RU via Django i18n or manual template blocks
