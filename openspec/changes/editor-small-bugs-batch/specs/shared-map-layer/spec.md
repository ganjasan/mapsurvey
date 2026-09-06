# shared-map-layer — delta for editor-small-bugs-batch

## ADDED Requirements

### Requirement: A question layer is backfilled from answers that already exist
When a `question`-sourced layer is created, and after responses are imported from a ZIP
archive, the system SHALL materialise the marks of every session (of every version) that
already answered the source geo question, under the same keys a section POST would use,
so the layer never reads "0 features" while answers exist.

#### Scenario: Layer created after collection started
- **WHEN** a survey has 16 point answers and the creator adds an Objects-on-the-map question sourced from that geo question
- **THEN** the new layer holds 16 objects immediately

#### Scenario: Responses imported from a ZIP
- **WHEN** an archive with structure, a question layer and responses is imported
- **THEN** the layer holds one object per imported mark
