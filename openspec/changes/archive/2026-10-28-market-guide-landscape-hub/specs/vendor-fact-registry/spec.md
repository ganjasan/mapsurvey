## ADDED Requirements

### Requirement: Every vendor fact is sourced and dated
The vendor registry (`survey/vendors.py`) SHALL hold, for every vendor and every selection criterion, a fact consisting of the rendered text, the public `https://` URL it was read from and the ISO date it was read. A fact the vendor's public page does not state SHALL be recorded as "Not published" with the URL of the page that was read. The registry SHALL refuse to import when a fact lacks a source URL, has a non-`https` source, has a date that does not parse or lies in the future, or when a vendor lacks a criterion or names a category that does not exist.

#### Scenario: Registry is complete and well-formed
- **WHEN** the registry is imported and every vendor is inspected
- **THEN** every vendor has a fact for every key in `CRITERIA`, every fact's source starts with `https://`, every `verified` value is an ISO date not after today, and every vendor's `category` is a key in `CATEGORIES`

#### Scenario: Not-published facts still carry a source
- **WHEN** a fact's text is "Not published"
- **THEN** its source URL and verified date are present like any other fact's

### Requirement: No price figures for other vendors in the registry
No fact text for a vendor other than Mapsurvey SHALL contain a currency figure. A pricing fact SHALL state the pricing model (per licence, per instance, per contributor, per project, quote only, free software), and a free-tier fact SHALL state whether a free tier or trial exists and its conditions, and whether a rate is listed publicly (the vendor's site, UK G-Cloud) or available from sales only.

#### Scenario: Registry facts carry only our own figures
- **WHEN** every fact text in the registry and the rendered hub page are scanned for currency figures
- **THEN** the only figures found are $0, $49 and $490

### Requirement: Alternatives pages render their comparison from the registry
`/alternatives/maptionnaire/`, `/alternatives/social-pinpoint/` and `/alternatives/metroquest/` SHALL render their comparison table from the registry through one shared partial, listing every criterion with the Mapsurvey fact and the vendor's fact, followed by a note linking the vendor's source pages and stating the verified date. The pages SHALL NOT claim EU hosting for Mapsurvey.

#### Scenario: Maptionnaire page cells come from the registry
- **WHEN** `/alternatives/maptionnaire/` is rendered
- **THEN** its hosting cell contains the registry's Maptionnaire hosting text ("AWS" and "Ireland"), the note links `maptionnaire.com`, the page contains "verified" with the vendor's date, and the page does not contain "Frankfurt" or "EU-hosted"

#### Scenario: Social Pinpoint page agrees with itself on export
- **WHEN** `/alternatives/social-pinpoint/` is rendered
- **THEN** the page contains "GeoJSON" in the export cell and does not contain "no GeoJSON export"

#### Scenario: A registry edit reaches every page
- **WHEN** the Maptionnaire export fact text is changed in the registry (in a test, by patching)
- **THEN** both `/participatory-mapping-tools/` and `/alternatives/maptionnaire/` render the new text
