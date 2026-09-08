## REMOVED Requirements

### Requirement: Local daily store for external acquisition metrics
**Reason**: Search Console and Bing are native PostHog warehouse sources since 2026-09-08; the
local store duplicated them with worse granularity and no country filter.
**Migration**: Read impressions, clicks and pages on the PostHog AARRR dashboard (id 941308) from
`googlesearchconsole_*` / `bingwebmastertools_*` tables. The `AcquisitionDaily` table is dropped.

### Requirement: Search Console ingestion split by page group
**Reason**: Superseded by the native PostHog Search Console source, whose `by_page_country` table
gives the same split as a query filter.
**Migration**: HogQL over `googlesearchconsole_search_analytics_by_page_country` with
`page NOT LIKE '%/surveys/%'` and `country != 'mar'`.

### Requirement: Plausible ingestion of landing traffic and channels
**Reason**: Plausible is cancelled; its landing series mixed in customers' respondents.
**Migration**: Landing visits come from PostHog `$pageview` on `/` with bots excluded (AARRR tile
A5); channel mix from `first_source_bucket` on persons once attribution is forwarded.

### Requirement: Idempotent, windowed synchronisation command
**Reason**: No providers left to synchronise.
**Migration**: `sync_acquisition_metrics` and the Render cron `mapsurvey-acquisition-sync` are
deleted; the cron resource is removed by hand in Render.

### Requirement: Per-source sync state and failure isolation
**Reason**: Sync state is PostHog's concern now (source status on the Sources page).
**Migration**: `AcquisitionSyncState` is dropped.

### Requirement: Missing credentials are a reported state, not an error
**Reason**: No provider credentials remain in this codebase.
**Migration**: `GSC_*` and `PLAUSIBLE_*` settings and env vars are removed; the PostHog source
holds its own OAuth/API key.
