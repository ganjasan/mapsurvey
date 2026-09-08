## MODIFIED Requirements

### Requirement: Capture signup source at registration
The system SHALL capture the acquisition source of a new creator — the first external HTTP referrer
(classified into a source bucket), any UTM parameters (`utm_source`, `utm_medium`, `utm_campaign`)
and the landing path seen on the marketing flow — and SHALL persist it associated with the created
user on successful registration. First-touch values SHALL be stored in a first-party cookie that
lives 90 days, holds no user identifier, and is written only on marketing pages; a referrer whose
host is the site's own host SHALL never be recorded as the source.

#### Scenario: Referrer and UTM captured on successful registration
- **WHEN** a visitor arrives with an external referrer and/or UTM parameters and completes
  registration
- **THEN** a `SignupAttribution` record is created for the new user storing the raw referrer, the
  classified source bucket, the UTM triple and the landing path

#### Scenario: First touch survives a gap before signup
- **WHEN** a visitor lands from an external source, closes the browser, and registers from a direct
  visit twelve days later
- **THEN** the `SignupAttribution` record carries the original external source, not `direct`

#### Scenario: Internal hop never overwrites the source
- **WHEN** a visitor moves from the landing page to `/accounts/register/` and the only referrer on
  the registration request is the site itself
- **THEN** the recorded source is the value captured earlier, or `direct` when nothing was captured
  — never the site's own host

#### Scenario: Direct visit with no referrer
- **WHEN** a visitor registers with no referrer and no UTM parameters
- **THEN** a `SignupAttribution` record is created with the `direct` source and empty UTM fields
  (absence of source is recorded, not an error)

#### Scenario: Respondent pages never set the cookie
- **WHEN** a request is served under `/surveys/` or `/r/`
- **THEN** no first-touch cookie is written

#### Scenario: UTM parsing reuses existing helpers
- **WHEN** UTM parameters are read from the landing request
- **THEN** the system uses the existing `store_utm_in_session` / `_consume_utm_from_session`
  helpers and the existing `_classify_referrer` helper rather than duplicating parsing logic

## ADDED Requirements

### Requirement: Referrer classification recognises AI assistants and secondary search engines
`_classify_referrer` SHALL return the bucket `ai` for referrers from AI assistants (at least
chatgpt.com, chat.openai.com, perplexity.ai, gemini.google.com, claude.ai, copilot.microsoft.com)
and `search_other` for search engines other than Google and Bing (at least duckduckgo.com,
search.brave.com, yahoo.com, ecosia.org, startpage.com). When the referrer yields `direct` or
`other` but `utm_source` names an AI assistant, the bucket SHALL be `ai`.

#### Scenario: ChatGPT referrer
- **WHEN** the referrer host is `chatgpt.com`
- **THEN** the bucket is `ai`

#### Scenario: ChatGPT without referrer but with its UTM
- **WHEN** there is no referrer and `utm_source=chatgpt.com`
- **THEN** the bucket is `ai`

#### Scenario: DuckDuckGo referrer
- **WHEN** the referrer host is `duckduckgo.com`
- **THEN** the bucket is `search_other`

#### Scenario: Google and Bing unchanged
- **WHEN** the referrer host is `www.google.de` or `www.bing.com`
- **THEN** the bucket is `google` or `bing` respectively

### Requirement: Attribution is forwarded to PostHog as first-touch person properties
On registration the `creator_registered` event SHALL carry a `$set_once` block with
`first_source_bucket`, `first_referrer_host`, `first_utm_source`, `first_utm_medium`,
`first_utm_campaign` and `first_landing_path` taken from the persisted `SignupAttribution`. The
values SHALL be set-once so a later write never replaces the first touch. Forwarding SHALL be
fail-open and SHALL NOT include the raw referrer URL.

#### Scenario: Registration event carries first touch
- **WHEN** a creator registers with a captured source
- **THEN** the emitted `creator_registered` event contains `$set_once` with the six first-touch
  properties and no raw referrer URL

#### Scenario: PostHog unavailable
- **WHEN** PostHog is unconfigured or the capture raises
- **THEN** registration and the `SignupAttribution` write complete normally

### Requirement: Existing attribution rows are backfilled to PostHog
The `sync_posthog_person_properties` command SHALL send the same six first-touch properties for
every existing `SignupAttribution` row using a set-once write, and SHALL offer a `--reclassify`
option that recomputes `source_bucket` from the stored `raw_referrer` and UTM with the current
classifier, treating the site's own host as `direct`, before sending.

#### Scenario: Spoiled rows are repaired before sending
- **WHEN** the command runs with `--reclassify` over a row whose `raw_referrer` host is the site
  itself and bucket is `other`
- **THEN** the row's bucket becomes `direct` (or the UTM-derived bucket) and that value is what
  reaches PostHog

#### Scenario: Backfill never overwrites a live value
- **WHEN** a person already has `first_source_bucket` set from a live registration
- **THEN** the backfill leaves it unchanged
