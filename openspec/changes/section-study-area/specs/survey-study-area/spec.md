## ADDED Requirements

### Requirement: A map section uses the survey's area, its own, or none
Each map section SHALL use one of: the survey's study area (the default), its own area, or no area.
An own area SHALL be a polygon validated, simplified and edited exactly like the survey's area and
SHALL carry its own fog, refusal rule and message. A section's choice SHALL be stored by section
reference (`<code>` or `<code>#<n>`) on the canonical survey, read by draft copies and versions and
never copied between them, and SHALL be a safe edit on a published survey. Switching a section away
from its own area SHALL keep the outline so switching back restores it. This requirement narrows
"applies to every map section": the survey's area applies to every map section that keeps the default.

#### Scenario: A corridor on the second section
- **WHEN** a survey's area is the city and its second map section is given an own area along one street
- **THEN** the first section uses the city and the second uses the street corridor

#### Scenario: No area on one section
- **WHEN** a section with a "where do you live" question chooses No area on a survey whose area refuses answers outside
- **THEN** that section draws no outline or fog and accepts marks anywhere, and the other sections still refuse

#### Scenario: The default
- **WHEN** a map section has never chosen
- **THEN** it uses the survey's area, and uses nothing when the survey has none

#### Scenario: Own area restored
- **WHEN** a section with an own area switches to Survey's area and then back to Own area
- **THEN** its own outline and rules are the ones it had

#### Scenario: Draft copy
- **WHEN** a section of a published survey's unpublished changes sets an own area
- **THEN** the choice is stored on the canonical survey and the live survey's section with the same reference uses it at once

### Requirement: Respondent surfaces use the section's effective area
Every respondent surface SHALL use the section's effective area — its own area, the survey's area, or
none: the respondent map, the browser refusal, the section POST refusal and the editor's Live preview. The respondent page
SHALL carry each section's effective area metadata with the section (outline URL, fog, rule,
message, bounds), never the geometry inline; when the next section's area differs the map SHALL
replace the outline and fog and open on the new area unless the section's own start lies inside it.
A refused mark SHALL be counted on the area that refused it.

#### Scenario: Moving to a section with another area
- **WHEN** a respondent moves from a section using the survey's area to a section with an own area
- **THEN** the old outline and fog are removed, the own outline is drawn and the map fits it

#### Scenario: Scripted mark on a section with no area
- **WHEN** a client posts a point far outside the survey's area on a section whose choice is No area, with the survey's refusal on
- **THEN** the point is stored and nothing is counted

#### Scenario: Scripted mark outside an own area
- **WHEN** a section's own area refuses answers outside and a client posts a point outside it but inside the survey's area
- **THEN** the point is not stored and the section's own refused counter grows by one

#### Scenario: Preview of a section with an own area
- **WHEN** the editor's Live preview renders a section with an own area
- **THEN** it carries that section's outline URL and rules

### Requirement: An own area's message is translatable creator text
An own area's refusal message SHALL be plain text listed in the Translations tab as the occurrence
`section:<ref>:study_area_message` while its refusal is on, and a respondent SHALL read it in the
survey language when a translation exists.

#### Scenario: German message of an own area
- **WHEN** a section's own area has an English message and the German row is written in the Translations tab
- **THEN** the own area keeps both messages and a German respondent on that section reads the German one

### Requirement: A section's choice is writable through every surface
The Map card, REST v1 and the MCP server SHALL read and set a map section's choice through the study
area service with each surface's role and Pro gates: `GET` / `PUT
/surveys/{uuid}/sections/{section_id}/study-area` and the MCP tools `get_section_study_area` and
`set_section_study_area` (`mode` `survey` | `own` | `none`; `own` with a geometry replaces the
outline, without one keeps the stored outline and is refused when there is none). The survey's
study area read SHALL list each map section's id, reference, title and choice. A section without a
map SHALL be refused.

#### Scenario: Own area through MCP
- **WHEN** an agent calls `set_section_study_area` with `mode: own`, a polygon and `refuse_outside: true`
- **THEN** the section uses that polygon with the rule on and the Map card shows Own area

#### Scenario: Own without an outline
- **WHEN** a client sets `mode: own` without a geometry on a section that never had one
- **THEN** the request is refused with a validation error and nothing changes
