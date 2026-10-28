## ADDED Requirements

### Requirement: Localized numbers never reach inline JavaScript

Every template SHALL render server-side values into inline JavaScript with
localization disabled — `{% localize off %}` around the block, or `|unlocalize` on the
value. Human-readable readouts outside `<script>` SHALL stay localized.

Ten of the eleven shipped creator languages write decimals with a comma, so a float
rendered under an active locale becomes `50,9375`: such a `<script>` block either fails to
parse or parses the wrong value, and stops running entirely.

This SHALL be enforced by a repository-wide check over the template source, not by
asserting against a list of rendered URLs: the defect recurred in September 2026 because
a template added after the guard was written was outside the URLs the guard named.

#### Scenario: An unguarded coordinate in a new template fails the suite

- **WHEN** any template under `survey/templates/` interpolates a server-side value inside a `<script>` block that is not wrapped in `{% localize off %}` and not filtered through `|unlocalize`
- **THEN** the test suite fails and names that file and the offending interpolation

#### Scenario: The layer object editor initialises in a comma-decimal language

- **WHEN** a creator whose UI language is German opens `/editor/surveys/<uuid>/layers/<id>/edit/` for a survey positioned at 50.9375, 6.9603
- **THEN** the inline script contains `50.9375` and `6.9603` with decimal points, the Leaflet map initialises, and moving the pointer over it raises no exception

#### Scenario: Coordinates are identical in every language

- **WHEN** the same page is rendered under English and under German
- **THEN** the numbers inside its `<script>` blocks are byte-identical in both

#### Scenario: Readouts stay localized

- **WHEN** a German creator views the coordinates label beneath a map picker
- **THEN** the label renders in the creator's locale, because it is outside the script block

#### Scenario: The detector itself is pinned

- **WHEN** a template fragment of the shape this defect produced is rendered under a comma-decimal locale with no guard
- **THEN** the detector fires, proving it is capable of failing
