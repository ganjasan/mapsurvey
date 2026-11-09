## ADDED Requirements

### Requirement: A site in several languages
A site SHALL offer its primary language and any added content languages. Its **Translations** tab SHALL list every creator-written text of the site once per identical text, in page order, with a status (missing, outdated, translated), and SHALL save a row, export and import CSV in the layout of the survey table. Translations SHALL be written only through the sites service: rich text through `coerce_creator_html`, plain text trimmed and capped, an empty value removing the translation, the source hash recorded so a later change of the source marks the row outdated. Members SHALL read and export; owners, admins and editors of a workspace that may use Sites SHALL save, import, add and stop offering languages; a language the site does not offer SHALL be refused.

The public page SHALL pick the language from `?lang=`, then a `p_lang` cookie set by an explicit choice, then the browser's Accept-Language, then the primary; it SHALL set `<html lang>`, list `hreflang` alternates and a language switch when more than one language is offered, and show the primary text wherever a translation is missing. An event registration SHALL remember the language for its confirmation mail and cancel page. Duplicating a site SHALL carry its languages and translations. Content screening SHALL read the translations.

#### Scenario: Visitor reads Spanish
- **WHEN** a site with a Spanish heading and body is opened with `?lang=es`
- **THEN** the page has `lang="es"`, the Spanish texts, the English text where no translation exists, a language switch and hreflang links, and remembers the choice in a cookie

#### Scenario: Browser language
- **WHEN** a visitor whose browser asks for `es-MX` opens the same site without `?lang`
- **THEN** the page is in Spanish

#### Scenario: Outdated translation
- **WHEN** the English heading changes after it was translated
- **THEN** the row reads outdated

#### Scenario: CSV round trip
- **WHEN** the exported CSV comes back with the Spanish column filled in
- **THEN** the translations are stored

#### Scenario: Rights and languages
- **WHEN** a viewer saves a row, or an editor saves into a language the site does not offer
- **THEN** the viewer gets 403 and the save 400
