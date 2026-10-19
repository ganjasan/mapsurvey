## ADDED Requirements

### Requirement: The picker dropdown is sized for browsing, not for its input
The icon picker's dropdown SHALL be at least 440 px wide. Where the viewport is narrower than that plus a 16 px margin, it SHALL be the viewport width less 16 px. Its width SHALL NOT depend on the width of the input it is attached to. On opening, it SHALL align to whichever edge of its input keeps it inside the viewport. Below 768 px it SHALL keep its existing full-width bottom placement. Grid cells SHALL be at least 44 px with glyphs of at least 22 px.

#### Scenario: Narrow table cell
- **WHEN** the picker of a choices-table Icon cell about 230 px wide is opened on a desktop
- **THEN** the dropdown is at least 440 px wide and fully inside the viewport

#### Scenario: Near the right edge
- **WHEN** the input sits so close to the right edge of the viewport that a left-aligned 440 px dropdown would overflow it
- **THEN** the dropdown aligns to the input's right edge instead
