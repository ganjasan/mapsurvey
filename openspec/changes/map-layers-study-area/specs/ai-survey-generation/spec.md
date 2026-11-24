## MODIFIED Requirements

### Requirement: Place prefill from the brief on the create map
The create page SHALL attempt to aim the map picker at a place named in the brief before
submission, on every viewport. Candidates SHALL be taken from the goal, audience, and
map-target fields. Every candidate SHALL be looked up and the one the geocoder ranks as the
most place-like (country, state, city, town, district, neighbourhood, street — in that order of
preference over a peak, a building or an unclassified point) SHALL win, not the first that
resolves, so a capitalised common noun ("Снега") never outranks the city named next to it. The
attempt SHALL run when the mobile wizard shows the map step, and on desktop after a pause in
typing in any brief field and once more when the draft action is triggered. The map SHALL only
be moved while the creator has not framed it themselves (dragged, zoomed by wheel, pinch,
double-click or zoom control, chosen a search result, or used "My location"); a prefill move or
a browser-geolocation move SHALL NOT count as the creator framing the map. A successful prefill
SHALL show the resolved place name in the map search box. The form SHALL post a hidden
`map_touched` field equal to `1` if and only if the creator framed the map.

#### Scenario: Desktop brief names a place
- **WHEN** a desktop creator types "Residents of Ülemiste City" into the audience field and pauses
- **THEN** the map moves to Ülemiste, the search box shows the resolved name, and `map_touched` stays unset

#### Scenario: A capitalised word before the city
- **WHEN** the goal reads "Хочу опрос на тему качества уборки Снега в Санкт-Петербурге, Россия"
- **THEN** the map moves to Saint Petersburg, not to a place called "Снега"

#### Scenario: Creator framed the map first
- **WHEN** the creator dragged the map and then types a place into the goal
- **THEN** the map does not move and `map_touched` is posted as `1`

#### Scenario: Geolocation jump does not lock the map
- **WHEN** the browser geolocation moved the map on page load and the creator then types a place into the brief
- **THEN** the prefill still moves the map to the named place and `map_touched` stays unset

## ADDED Requirements

### Requirement: The Wizard names the survey
The generation response SHALL carry a `survey_name`: a title of at most 40 characters in the
survey's primary language that names the topic and, when the brief names one, the place. When the
creator did not type a name — the create page filled it from the start of the goal or with
"Untitled survey" — the drafted survey SHALL take the model's title, and the user turn SHALL NOT
present the derived text as the survey name. A name the creator typed SHALL be kept. The title SHALL
be normalised (whitespace collapsed, surrounding quotes and a trailing full stop removed, cut at a
word boundary to 45 characters); a title without a letter or digit SHALL be dropped, keeping the
derived name, and SHALL never cause a retry.

#### Scenario: Name cut from the goal is replaced
- **WHEN** the goal is "Хочу опрос на тему качества уборки Снега в Санкт-Петербурге, Россия." and the name field was left empty
- **THEN** the drafted survey is named by the model, e.g. "Уборка снега в Санкт-Петербурге", not "Хочу опрос на тему качества уборки Снега в С"

#### Scenario: A typed name is kept
- **WHEN** the creator typed the name "elm_street_2027"
- **THEN** the drafted survey keeps it, whatever title the model returns

#### Scenario: An unusable title
- **WHEN** the model returns "—" as the title
- **THEN** the draft succeeds with the derived name

### Requirement: The Wizard sets the study area
Whenever the brief names a place, the Wizard SHALL give the new survey a study area (owner,
2026-11-24: always). On the create page, once the map is aimed at a place (prefill or a search
result), its OpenStreetMap boundary SHALL be looked up through the study area lookup and drawn on
the create map with the fog the respondent will see, under a "Study area" strip that names the
place and offers the creator's handles: *Edit outline* (move, add, remove corners on the create
map), the corridor width (50 / 100 / 200 m) when the place is a street, *Map answers outside:
Allowed / Not allowed*, and *Remove*. The form SHALL post the outline the creator sees
(`study_area_geometry`, with its place name and OSM reference) or `study_area_mode=off` when they
removed it. When the form carries no outline (the lookup did not answer in time, or JavaScript
is off) and the creator did not remove it, generation SHALL look up the boundary of the place the
model read from the brief and set it. A study area set by the Wizard SHALL have fog on and
answers outside allowed unless the creator chose *Not allowed*; it SHALL be set through the study
area service after the draft is materialized, and a lookup that fails SHALL leave the survey
without a study area, never fail the draft. The create page's empty-survey path SHALL keep the
outline the strip shows the same way.

#### Scenario: A city brief gets its boundary
- **WHEN** a creator writes "Уборка снега в Санкт-Петербурге" and drafts the survey without touching the strip
- **THEN** the create map shows Saint Petersburg's outline with fog outside, and the drafted survey has that study area with fog on and answers outside allowed

#### Scenario: The creator edits the outline in the Wizard
- **WHEN** the creator clicks *Edit outline*, drags two corners and drafts the survey
- **THEN** the survey's study area is the edited outline with source `place`

#### Scenario: A street becomes a corridor in the Wizard
- **WHEN** the creator searches "North Highland Avenue, Atlanta" in the create map's search box and picks 50 m
- **THEN** the strip shows a 50 m corridor and the survey gets that corridor as its study area

#### Scenario: The creator removes the boundary
- **WHEN** the creator clicks *Remove* in the strip and drafts the survey
- **THEN** the survey has no study area, even though the brief names a place

#### Scenario: No outline in the form
- **WHEN** the draft request carries neither an outline nor `study_area_mode=off`, and the model reads "Tallinn, Estonia" from the brief
- **THEN** generation looks up Tallinn's boundary and the survey gets it as its study area

#### Scenario: The lookup is down
- **WHEN** OpenStreetMap does not answer during generation
- **THEN** the draft is created as usual, without a study area
