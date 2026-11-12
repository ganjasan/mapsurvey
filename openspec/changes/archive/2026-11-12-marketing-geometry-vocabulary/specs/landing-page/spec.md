## ADDED Requirements

### Requirement: Map input described in creators' words
Every marketing page (the homepage and every page extending `base_landing.html`, the SEO landing registry's FAQ answers, the vendor registry's criteria and Mapsurvey's facts, and the blog articles) SHALL describe what respondents do on the map with the words creators use in their own questions: *mark a place* or *pin* for point input, *draw a route* for line input, *outline an area* for polygon input, and the nouns *places*, *routes* and *areas*. The GIS terms *point*, *line* and *polygon* SHALL appear only where they name the data a creator gets back — the export sentence, file formats, field-collection tools' own terms and research (PPGIS) wording — never as the name of what a respondent does.

#### Scenario: Hero badges speak the creators' words
- **WHEN** `/community-engagement-platform/` or `/civic-engagement/` is rendered
- **THEN** its hero badge names places, routes and areas and does not contain "Point, line and polygon input"

#### Scenario: Mapsurvey's comparison cell
- **WHEN** a page renders the "What a respondent can draw" row
- **THEN** Mapsurvey's cell names places, routes and areas, each with follow-up questions

#### Scenario: Export keeps the GIS terms
- **WHEN** a page describes what the creator downloads
- **THEN** it may name points, lines and polygons as the GeoJSON, GeoPackage or Shapefile geometry
