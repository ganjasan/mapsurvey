## ADDED Requirements

### Requirement: Marker icon values round-trip verbatim
Export SHALL write `icon_class` exactly as stored, including `maki:`/`temaki:` values. Import
SHALL store the value verbatim (subject only to the existing 80-character truncation) without
validating it against the icon catalog, so an archive produced by a newer catalog imports on an
older one and renders the fallback pin rather than failing.

#### Scenario: Map-set value survives export and import
- **WHEN** a question with `icon_class` `maki:bench` is exported and the archive is imported
- **THEN** the imported question stores `maki:bench`

#### Scenario: Unknown value is preserved
- **WHEN** an archive carries `icon_class` `temaki:future-icon` that the catalog does not know
- **THEN** import succeeds and stores the value unchanged
