## ADDED Requirements

### Requirement: A site can be duplicated
An owner, admin or editor SHALL be able to duplicate a site from the Sites list and from Site settings. The copy SHALL be a new unpublished site titled "<title> (copy)" with a fresh address, the original's settings (language, width, visibility, cover and its description), survey links, and blocks in order with their headings, menu flags, data, pictures and document files; stored files SHALL be shared, not re-uploaded. Event registrations SHALL never be copied. Survey cards and results blocks of the copy SHALL point at the copy's own survey links. Duplicating SHALL be a Pro use exactly like creating a site.

#### Scenario: Copy for the next engagement
- **WHEN** an editor duplicates a published site with a survey card, an event with registrations and a documents block
- **THEN** a new unpublished site opens in the builder with the same blocks, its survey card on its own link, the same stored file, and no registrations

#### Scenario: Viewer cannot duplicate
- **WHEN** a viewer posts the duplicate action
- **THEN** the answer is 403 and no site is created

#### Scenario: Free workspace refused
- **WHEN** a member of a workspace without Pro and with its trial used duplicates a site
- **THEN** no site is created and the Pro offer is shown
