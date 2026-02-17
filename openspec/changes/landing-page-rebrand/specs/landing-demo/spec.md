## ADDED Requirements

### Requirement: Interactive demo section
The landing page SHALL display a demo section that lets visitors experience the product without registration.

#### Scenario: Primary variant — live iframe
- **WHEN** the landing page is rendered and a demo survey URL is configured
- **THEN** the demo section SHALL embed an iframe pointing to the live demo survey on mapsurvey.org

#### Scenario: Fallback variant — video or GIF
- **WHEN** the landing page is rendered and no demo survey URL is configured
- **THEN** the demo section SHALL display a video or animated GIF showing the survey creation → filling → export workflow

#### Scenario: Demo caption
- **WHEN** the demo section is rendered
- **THEN** a caption SHALL be displayed below the embed: "This is a live survey. Try it — then create your own in 2 minutes."

### Requirement: Demo section configuration
The demo survey URL SHALL be configurable via Django settings.

#### Scenario: Setting available
- **WHEN** `DEMO_SURVEY_URL` is set in Django settings
- **THEN** the demo section SHALL embed that URL in an iframe

#### Scenario: Setting absent
- **WHEN** `DEMO_SURVEY_URL` is not set or empty
- **THEN** the demo section SHALL fall back to the video/GIF variant

### Requirement: Demo iframe responsive sizing
The demo iframe SHALL be responsive and maintain usable proportions across screen sizes.

#### Scenario: Desktop sizing
- **WHEN** the demo section is rendered on a viewport >= 1024px
- **THEN** the iframe SHALL be at least 800px wide and 600px tall

#### Scenario: Mobile sizing
- **WHEN** the demo section is rendered on a viewport < 768px
- **THEN** the iframe SHALL fill the viewport width with a 4:3 or 16:9 aspect ratio

### Requirement: Demo section i18n support
The demo section caption SHALL support English and Russian.

#### Scenario: Bilingual caption
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** the demo caption text SHALL render in the active language
