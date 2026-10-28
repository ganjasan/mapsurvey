## MODIFIED Requirements

### Requirement: Custom thanks page content with language support
The system SHALL let survey creators author the thanks-page content with a
rich-text (WYSIWYG) editor, one body per available language, stored in
`SurveyHeader.thanks_html` (a `{lang: html}` JSONField; a plain string is still
accepted for back-compat). The editor output SHALL be sanitized server-side
against a tag/attribute allow-list before it is stored, so the public thanks page
can render it `|safe` without a stored-XSS risk. Language resolution SHALL follow
the existing chain (session language → `en` → first available).

#### Scenario: Empty thanks_html shows default message
- **WHEN** `thanks_html` is empty (`{}`)
- **THEN** the thanks page displays the default "Thank you" message with a "Take survey again" link

#### Scenario: Multilingual thanks_html resolves by session language
- **WHEN** `thanks_html` is `{"en": "<h1>Thanks!</h1>", "ru": "<h1>Спасибо!</h1>"}`
- **AND** the user completed the survey in Russian (`survey_language` is `"ru"`)
- **THEN** the thanks page renders `<h1>Спасибо!</h1>`

#### Scenario: Language fallback chain
- **WHEN** `thanks_html` is `{"en": "<h1>Thanks!</h1>"}` and the user finished in French
- **THEN** the thanks page falls back to `"en"`

#### Scenario: Plain string thanks_html for single-language surveys
- **WHEN** `thanks_html` is a plain string
- **THEN** the thanks page renders that string regardless of language

#### Scenario: WYSIWYG output is sanitized on save
- **WHEN** a creator saves thanks content containing a disallowed construct (e.g. a `<script>` or an `onclick` attribute)
- **THEN** the stored `thanks_html` has it stripped, keeping only allow-listed formatting (headings, bold/italic/underline, links with safe attributes, lists, blockquote, paragraphs)

#### Scenario: Session language is read before cleanup
- **WHEN** user arrives at the thanks page with `survey_language` in session
- **THEN** the view reads the language for content resolution before clearing the session

## ADDED Requirements

### Requirement: Thanks page is edited as the last step of Build
The Build space SHALL expose the thanks page as a pinned **"Thanks page"** entry
at the bottom of the sections sidebar (below the section list), selecting which
swaps a dedicated thanks editor into the center panel (the same panel mechanism
as "Survey settings"). The raw `thanks_html` field SHALL NOT appear in the Survey
settings panel. The editor SHALL autosave and SHALL show a live preview
approximating what respondents see, including the fixed share action and the
Mapsurvey branding footer.

#### Scenario: Thanks page entry opens the editor
- **WHEN** an editor clicks the pinned "Thanks page" entry in Build
- **THEN** the center panel swaps to the WYSIWYG thanks editor without a full reload

#### Scenario: Thanks content is no longer in Survey settings
- **WHEN** an editor opens the Survey settings panel
- **THEN** there is no raw "Thanks html" field there

#### Scenario: Language tabs for multilingual surveys
- **WHEN** the survey has more than one available language
- **THEN** the thanks editor offers a language switch that binds the editor to that language's `thanks_html[lang]`

#### Scenario: Thanks page shown in the Build live-preview pane
- **WHEN** the thanks editor is opened
- **THEN** the Build right-hand live-preview pane renders the actual thanks page (in the selected preview language, via an editor-only preview endpoint), and it refreshes after an autosave to reflect the edited content

### Requirement: Thanks page always carries mandatory Mapsurvey branding
The public thanks page SHALL always render the "Made with Mapsurvey" branding
link, regardless of any creator setting, and the thanks editor's preview SHALL
show it as a fixed, non-editable footer.

#### Scenario: Branding shown even when content is custom
- **WHEN** a respondent reaches the thanks page of any survey
- **THEN** the "Made with Mapsurvey" link is present below the content and share action

#### Scenario: Creator cannot remove branding from the thanks editor
- **WHEN** a creator edits the thanks page
- **THEN** the branding footer is shown in the preview and cannot be deleted or turned off
