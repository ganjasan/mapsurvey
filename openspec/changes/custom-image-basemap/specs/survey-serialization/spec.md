## ADDED Requirements

### Requirement: Image basemap serialization
A survey ZIP export (modes `structure` and `full`) SHALL carry the survey's image basemap, and import
SHALL restore it after running the file through the same validation and processing as a web upload.

#### Scenario: Export includes the image
- **WHEN** a survey with an uploaded image basemap is exported
- **THEN** `survey.json` includes `basemap_mode` and `image_basemap` with `file`, `width` and `height`
- **AND** the file is stored in the archive under `basemap/`

#### Scenario: Export without an image
- **WHEN** a survey that never uploaded an image is exported
- **THEN** `image_basemap` is null and `basemap_mode` is `tiles`

#### Scenario: Import restores the image
- **WHEN** an archive exported from an image-basemap survey is imported
- **THEN** the new survey uses the image basemap with the same picture and dimensions

#### Scenario: Missing basemap file in archive
- **WHEN** `survey.json` references a basemap file that is not in the archive
- **THEN** the survey is imported with `basemap_mode` `tiles` and the import report includes "Basemap image '<file>' not found in archive"

#### Scenario: Invalid basemap file in archive
- **WHEN** the archived basemap file is not a decodable image or exceeds the pixel limit
- **THEN** the survey is imported with `basemap_mode` `tiles` and the import report names the reason

#### Scenario: Archives from before this change
- **WHEN** an archive without `image_basemap` or `basemap_mode` is imported
- **THEN** the survey is imported with `basemap_mode` `tiles` and no warning
