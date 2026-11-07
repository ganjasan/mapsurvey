## MODIFIED Requirements

### Requirement: The print tab shows the last saved version
The editor SHALL show a *Print* tab with the Static Images frame of the latest **ready** version at the picked survey's frame. The frame SHALL start in greyscale, because paper forms are printed in black and white or photocopied, with an unchecked "In colour" toggle that shows the colour print. The editor SHALL say when unsaved changes or a pending version mean the print view lags behind.

#### Scenario: Print frame URL
- **WHEN** the editor renders for a style whose latest ready version is `artemkonuchov/abc` and the picked survey starts at (55.68, 12.57) zoom 13
- **THEN** the print tab's image URL names that style id, the frame's centre and `fresh=true`

#### Scenario: Print frame starts black and white
- **WHEN** the editor renders
- **THEN** the print frame is greyscale and the "In colour" toggle is unchecked
