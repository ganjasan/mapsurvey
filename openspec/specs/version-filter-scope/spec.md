# version-filter-scope Specification

## Purpose
TBD - created by archiving change version-filter-parity. Update Purpose after archive.
## Requirements
### Requirement: One resolution of the version filter serves every surface

The `version` request parameter SHALL be resolved by a single shared function. Every creator-facing
surface that reports responses — the analytics dashboard and its partials, and the data export —
SHALL resolve the same parameter value to the same set of survey versions.

#### Scenario: Analytics and export agree with no parameter

- **WHEN** a survey with a current version and archived versions is opened in analytics with no
  `version` parameter, and its data is downloaded with no `version` parameter
- **THEN** both cover the same set of sessions

#### Scenario: Analytics and export agree on every accepted value

- **WHEN** the same `version` value is passed to analytics and to the export
- **THEN** both resolve it to the same set of survey versions

### Requirement: The default scope is the whole version family

When no `version` parameter is supplied, both surfaces SHALL report the survey's whole version
family — the canonical survey plus its archived versions.

#### Scenario: Export with no parameter covers the family

- **WHEN** data is downloaded for a survey with archived versions and no `version` parameter
- **THEN** the export contains the responses of every version in the family

#### Scenario: A single-version survey is unaffected

- **WHEN** data is downloaded for a survey that has no archived versions and no `version` parameter
- **THEN** the export contains that survey's responses
- **AND** the filenames carry no version prefix

### Requirement: `latest` names the canonical version on every surface

The value `latest` SHALL resolve to the canonical (current) version alone, identically to `vN`
where N is the canonical version number.

#### Scenario: `latest` narrows analytics

- **WHEN** analytics is opened with `version=latest` on a survey with archived versions
- **THEN** only the canonical version's sessions are reported

#### Scenario: `latest` and the explicit current version agree

- **WHEN** `version=latest` and `version=vN` (N = the canonical version number) are requested on the
  same surface
- **THEN** both resolve to the canonical version alone

### Requirement: An explicit version resolves to that version alone

A value of the form `vN` or `N` SHALL resolve to the family member with that version number.

#### Scenario: An archived version is selected

- **WHEN** `version=vM` names an archived version of the survey
- **THEN** only that archived version's sessions are reported

#### Scenario: The canonical version is selected

- **WHEN** `version=vN` names the canonical version
- **THEN** only the canonical version's sessions are reported

### Requirement: Unrecognised values fall back to the default on every surface

A `version` value that cannot be resolved SHALL fall back to the default scope — this covers
unparseable text and version numbers that do not exist in the family. The fallback SHALL be the same
on every surface; no surface may narrow while another widens.

#### Scenario: Unparseable value

- **WHEN** `version=bogus` is passed to analytics and to the export
- **THEN** both report the whole version family

#### Scenario: A version number outside the family

- **WHEN** `version=v99` is passed on a survey whose highest version is lower
- **THEN** both report the whole version family

### Requirement: Export filenames are prefixed only when the scope spans versions

When the resolved scope contains more than one version, each version's exported files SHALL be
prefixed `vN_`. When it contains exactly one, filenames SHALL carry no prefix.

#### Scenario: Family scope prefixes each version

- **WHEN** a survey with a canonical and an archived version is exported with `version=all`
- **THEN** the archive contains one prefixed file set per version

#### Scenario: Single-version scope carries no prefix

- **WHEN** `version=all` is requested on a survey that has no archived versions
- **THEN** the exported filenames carry no version prefix

### Requirement: The analytics Download action exports what the page reports

The Download action on the analytics dashboard SHALL carry the version scope currently selected on
that page.

#### Scenario: Download follows the version picker

- **WHEN** a creator selects a version in the analytics version picker and then uses the page's
  Download action
- **THEN** the exported data covers that version scope

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

