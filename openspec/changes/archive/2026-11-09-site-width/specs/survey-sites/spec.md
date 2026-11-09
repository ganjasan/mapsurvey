## ADDED Requirements

### Requirement: Page width and full-width blocks
A site SHALL have a page width — `narrow`, `standard` or `wide` (760, 960 or 1200 px of column) — set in Site settings and defaulting to `narrow`; the public page, its header and menu, and the builder's canvas SHALL use it. Image, video and map blocks SHALL offer **Full width**: the picture, player or map then spans the page up to 1400 px while the block's heading and caption stay in the column. A width or flag outside these values SHALL be ignored.

#### Scenario: Wide site
- **WHEN** an editor sets the page width to Wide and publishes
- **THEN** the public page carries `data-width="wide"` and the builder's canvas the same

#### Scenario: Full-width map
- **WHEN** a map block is saved with Full width ticked
- **THEN** the block stores `wide: true` and renders with the full-width class on the public page

#### Scenario: Unknown width ignored
- **WHEN** the settings are posted with width `huge`
- **THEN** the site keeps its width
