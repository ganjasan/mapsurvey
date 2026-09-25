## MODIFIED Requirements

### Requirement: Creator artwork is publicly readable
Creator artwork SHALL be anonymously readable by URL.

Images a creator authors — survey covers, question images, story covers, results-page images, and
processed survey image basemaps — SHALL be anonymously readable by URL, because they are already
shown openly on every survey and public results page. An image basemap upload that has not yet been
validated is not creator artwork and SHALL be stored on the private tier until processing replaces
it with the public copy.

#### Scenario: Artwork is publicly readable

- **WHEN** an unauthenticated client requests a stored creator image by URL
- **THEN** the object is returned

#### Scenario: Processed image basemap is publicly readable

- **WHEN** an unauthenticated client requests a survey's processed image basemap by URL
- **THEN** the object is returned

#### Scenario: A key outside the artwork prefixes is not publicly readable

- **WHEN** an unauthenticated client requests an object stored outside the creator-artwork prefixes
- **THEN** the request is denied

#### Scenario: Unvalidated basemap upload is not publicly readable

- **WHEN** an unauthenticated client requests the storage key of a basemap upload awaiting processing
- **THEN** the request is denied
