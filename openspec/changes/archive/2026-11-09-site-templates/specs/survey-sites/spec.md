## ADDED Requirements

### Requirement: Sites start from templates
The Sites list SHALL offer *From a template* next to *New site* with the Mapsurvey starters (Consultation, Master plan) and the workspace's own templates. A starter SHALL create a draft site whose blocks pass the same validation as any block, with the blocks that need the creator's material added empty. *Save as template* SHALL create a copy of a site marked as a template, without survey links (its survey cards and results blocks kept, empty) and without event registrations; starting from it SHALL copy its blocks into a new draft. A template SHALL never be published or opened publicly. Starting a site from a starter or a template SHALL count as a Sites use; a template of another workspace SHALL be refused.

#### Scenario: Master plan starter
- **WHEN** an editor picks the Master plan starter
- **THEN** a draft opens with heading, text, map, timeline, survey card, heading, results, documents and contacts blocks, the text and phases filled in

#### Scenario: Workspace template
- **WHEN** a site with a survey card is saved as a template and a new site is started from it
- **THEN** the template keeps both blocks without survey links, publishing it is refused, its address is 404, and the new site has the same blocks

#### Scenario: Another workspace's template
- **WHEN** an editor posts the template of another workspace
- **THEN** the answer is 404 and nothing is created

#### Scenario: Trial used up
- **WHEN** a free workspace whose trial is used picks a starter
- **THEN** no site is created
