## ADDED Requirements

### Requirement: A list of versions resolves to exactly those versions

A `version` value containing commas SHALL be read as a list of entries, each of the forms a single
value accepts (`vN`, `N`, `latest`). The scope SHALL be the family members those entries name, each
once, in family order (canonical first, then archived newest-first), whatever order the list gives.
Entries that name no family member SHALL be dropped. An `all` entry SHALL widen the scope to the
whole family. A `draft` entry SHALL be ignored, so preview data never joins a published scope. A
list in which nothing resolves SHALL fall back to the whole family, as a single unrecognised value
does. A list that resolves to one version SHALL behave as that single value. The same resolution
SHALL serve the export, the Responses page, the REST API and the MCP server.

#### Scenario: Two archived versions out of many

- **WHEN** a survey with versions v1–v11 (v11 canonical) is exported with `version=v10,v11`
- **THEN** the export contains only the sessions answered on v10 and v11, in every format

#### Scenario: List order and duplicates do not matter

- **WHEN** `version=v10,v11,11` and `version=v11,v10` are resolved on the same survey
- **THEN** both resolve to the same two versions, canonical first

#### Scenario: Unknown entries are dropped

- **WHEN** `version=v10,v99,bogus` is resolved on a survey with versions v1–v11
- **THEN** the scope is v10 alone and its files carry no prefix

#### Scenario: Nothing in the list resolves

- **WHEN** `version=v98,v99` is resolved
- **THEN** the scope is the whole version family

#### Scenario: Draft never joins a list

- **WHEN** `version=draft,v10,v11` is resolved on a survey that has a draft copy
- **THEN** the scope is v10 and v11, without the draft copy

#### Scenario: Several versions keep the prefixes

- **WHEN** a survey is exported with `version=v10,v11`
- **THEN** each version's files and layers are prefixed `v10_` and `v11_`, as with `version=all`

#### Scenario: Old values unchanged

- **WHEN** an export is requested with `version=all`, with `version=v10`, or with no `version`
- **THEN** it contains exactly what the same request contained before lists were accepted
