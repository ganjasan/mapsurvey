## ADDED Requirements

### Requirement: Story pictures open in a lightbox
On the story detail page every picture of the story (cover and body figures) SHALL open, on
click, in a lightbox showing the picture at up to viewport size with its caption (the figure's
caption, else the alt text), a position counter, previous/next controls that wrap within the
story, and a close control. The lightbox SHALL close on the close control, on Escape and on a
click outside the picture; the arrow keys SHALL step between pictures. The credit logo is not a
story picture.

#### Scenario: Open and read the caption
- **WHEN** a visitor clicks the route-map figure in a story
- **THEN** the lightbox shows that image with the figure's caption and a counter such as "3 / 12"

#### Scenario: Step to the next picture
- **WHEN** the lightbox is open and the visitor presses the next control or the right arrow key
- **THEN** the lightbox shows the following picture of the same story, wrapping to the first
  after the last

#### Scenario: Close
- **WHEN** the visitor presses Escape, the close control, or clicks the backdrop
- **THEN** the lightbox closes and focus returns to the picture that opened it

#### Scenario: Story without pictures
- **WHEN** a story with no pictures is rendered
- **THEN** the page renders normally and the lightbox is never shown
