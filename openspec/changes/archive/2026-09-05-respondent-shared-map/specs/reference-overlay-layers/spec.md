## MODIFIED Requirements

### Requirement: Layer geometry is served by a gated cacheable endpoint
Layer GeoJSON SHALL be served at `GET /surveys/<uuid>/layers/<id>.geojson` under the
same access rules as the survey's section pages. For `upload` layers the response SHALL
carry an `ETag` derived from the layer's `updated_at` and private caching. For `question`
layers the response SHALL be computed per request — only `visible` objects from clean
sessions other than the requesting session — with an `ETag` that also includes the
requesting session id and `Cache-Control: private, no-store`. The served document SHALL be
the GeoJSON derived from the layer's objects, carrying the reserved `_key`, `_title`,
`_category`, `_has_content` and `_cover` properties, plus `tally_up`, `tally_down` and
`comment_count` on `question` layers with `show_tallies`. Layer GeoJSON SHALL NOT be
inlined into the respondent HTML and SHALL NOT be exposed at a public storage URL. Layers
SHALL resolve to the canonical survey for draft copies and archived versions.

#### Scenario: Draft survey layer hidden from outsiders
- **WHEN** an anonymous request fetches a layer of an unpublished survey without a test link
- **THEN** the endpoint refuses as the survey page itself would

#### Scenario: Conditional revalidation
- **WHEN** a client re-requests an `upload` layer with a matching `If-None-Match`
- **THEN** the endpoint returns 304 with no body

#### Scenario: Version reads canonical layers
- **WHEN** a respondent loads an archived version's page (or a creator loads a draft copy's preview)
- **THEN** the layer list and geometry are the canonical survey's

#### Scenario: Question layer is per session
- **WHEN** two respondents fetch the same `question` layer
- **THEN** each receives a collection without their own marks, the ETags differ, and neither response is stored by a shared cache
