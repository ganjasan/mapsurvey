## ADDED Requirements

### Requirement: Popups open clear of the panel and the search box
A respondent map popup (a placed feature's sub-question form, or an object card) SHALL auto-pan so it opens fully inside the visible map: on desktop not under the survey panel that overlays the map, and not under the address search box at the map's top edge. The popup's content SHALL not overflow horizontally.

#### Scenario: Object card opened from the list on desktop
- **WHEN** a respondent on a desktop viewport opens an object from the panel list and the object sits near the panel
- **THEN** the map pans so the whole card is to the right of the panel and below the search box
- **AND** the card has no horizontal scrollbar and none of its text is cut off

#### Scenario: Phone
- **WHEN** the viewport is a phone
- **THEN** no panel padding applies, because the panel slides away before the popup opens
