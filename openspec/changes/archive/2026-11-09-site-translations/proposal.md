## Why

Issue #618 (epic #348, Sites v1.1 wave B, story S2). Engagements run in several languages — Druid Park ran English and Spanish and we translated by hand; consultancies work abroad; councils serve minority languages. A site existed in one language only.

## What Changes

- **Languages**: a site offers its primary language plus any of the 75 content languages (`Site.languages`), added from its **Translations** tab (builder top bar) and removed there ("Stop offering" keeps the stored translations).
- **Translations tab**: the survey translation table over a site — every heading, text, FAQ question and answer, phase, caption, button label, event place and description, contact role, address and hours, file title, the site title, summary and cover description, in page order; one translation fills every place the same text is used; statuses missing / outdated / translated; CSV export and import; same page script and row partial.
- **Storage**: JSON on the rows (`Site.translations`, `SiteBlock.translations`, hashes in `Site.translation_sources`), keys by block id (`block:<pk>:<field>`) — a site has no draft copy or versions, so ids are stable; duplicating a site carries its translations, file titles remapped. Written only by `services.sites.set_translations` (rich text through `coerce_creator_html`, plain text capped).
- **Public page**: the language comes from `?lang=`, then the `p_lang` cookie (set by an explicit choice), then Accept-Language, then the primary; `<html lang>`, `hreflang` alternates, a language switch in the header; untranslated texts show in the primary language; fixed labels in the chosen language. Event registrations remember the language and the confirmation mail and cancel page use it.
- **Screening** reads the translations with the rest of the site's text.
- Not in this change: opening a linked survey directly in the visitor's language (the survey's own language page still asks), AI drafts of translations.

## Capabilities

### Modified Capabilities
- `survey-sites`: a site can be offered and read in several languages.

## Impact

Migration `0125_site_translations` (JSON columns and `EventRegistration.language`, all with `db_default`); new `site_translations.py`, `site_translation_views.py`, `sites/translations.html`; `services/sites.py`, `site_views.py`, `site_events.py`, `content_screening.py`, `sites.py` (duplicate), `public.html`, `blocks/documents.html`, `blocks/event.html`, `event_cancel.html`, `_translation_link.html`, builder top bar, CSS, help, catalogs.
