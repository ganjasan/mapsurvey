## ADDED Requirements

### Requirement: Acquisition is read in PostHog
The staff funnel dashboard SHALL show, in place of the former acquisition block, a card linking to
the PostHog AARRR dashboard that names what lives there (search impressions and clicks, landing
visits, channel mix) and states that top-of-funnel numbers are no longer computed in this
application.

#### Scenario: Card renders
- **WHEN** a staff user opens the funnel dashboard
- **THEN** the acquisition position shows the link card and no impressions, visits, channel or
  freshness figures

## REMOVED Requirements

### Requirement: Top-of-funnel acquisition block
**Reason**: Provider data now lives in PostHog's warehouse; rendering it here required a second
sync pipeline.
**Migration**: PostHog AARRR dashboard, Acquisition row.

### Requirement: Acquisition stages reflect source availability
**Reason**: No locally stored provider metrics remain.
**Migration**: Source health is shown on PostHog's Sources page.

### Requirement: Acquisition channel breakdown
**Reason**: Plausible channel data is gone; a better breakdown (by first-touch bucket, through to
publication) is a PostHog insight.
**Migration**: PostHog insight on `first_source_bucket`; registrations-by-source on this dashboard
still reads `SignupAttribution`.

### Requirement: Synchronisation freshness is visible on the dashboard
**Reason**: Nothing is synchronised by this application any more.
**Migration**: PostHog Sources page.
