## MODIFIED Requirements

### Requirement: Help entry point in the editor header
Pages built on `base.html` and `editor/editor_base.html` SHALL show a "?" help control in the header for signed-in creators (desktop widths; phones keep "Help & support" in the ⋯ and account menus). It SHALL open a menu — "What's new", "Help centre", then "Help & support" with a line setting the reply expectation — rather than the chat itself. "Help centre" SHALL link to the help site home from the help-links registry (`HELP_URL.help_home`) and open in a new tab; when `HELP_SITE_URL` is empty the item SHALL be omitted. When the chat is unconfigured the menu SHALL offer `mailto:CONTACT_EMAIL` instead of "Help & support".

#### Scenario: Configured chat
- **WHEN** a signed-in creator opens an editor page and `CHATWOOT_WEBSITE_TOKEN` is set
- **THEN** the header carries the "?" menu with "Help & support" calling `openSupportChat` and the reply-expectation line

#### Scenario: Unconfigured chat
- **WHEN** a signed-in creator opens an editor page and `CHATWOOT_WEBSITE_TOKEN` is empty
- **THEN** the "?" menu offers an email link to `CONTACT_EMAIL` and no chat entry

#### Scenario: Help centre link
- **WHEN** a signed-in creator opens an editor page and `HELP_SITE_URL` is set
- **THEN** the "?" menu carries "Help centre" linking to `HELP_SITE_URL` with `target="_blank"` and `rel="noopener"`, and no link to `#faq` is rendered

#### Scenario: Help site disabled
- **WHEN** `HELP_SITE_URL` is empty
- **THEN** the "?" menu shows "What's new" and the support entry only
