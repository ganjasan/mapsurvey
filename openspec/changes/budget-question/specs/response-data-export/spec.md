## ADDED Requirements

### Requirement: Budget answers export as one column per item plus a total; priced marks carry their cost

A `budget` question SHALL export one column per item followed by a total column: in `split`
mode the item column holds the amount and its header carries the symbol
(`<question>: <item> (£)`); in `projects` mode it holds `1` or `0`. A respondent who did not
answer SHALL leave the columns empty. Every mark of a priced geo question under a budget group
SHALL carry a `cost` property in the GeoJSON, GeoPackage, Shapefile and KML layers and the
observations table, and the flat table SHALL hold one `<group>: spent (£)` column per budget
group with what that respondent's marks cost together.

#### Scenario: Split columns

- **WHEN** a survey with a five-item Split question is exported as CSV
- **THEN** the table carries five amount columns and a total column for that question

#### Scenario: Priced marks in GeoJSON

- **WHEN** a 200 m path priced £5 a metre is exported
- **THEN** its feature's properties include `cost` ≈ 1000 and the respondent's row a `spent` column
