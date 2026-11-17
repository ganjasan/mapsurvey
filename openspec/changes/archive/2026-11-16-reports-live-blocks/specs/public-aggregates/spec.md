## ADDED Requirements

### Requirement: Only a report's author can lift the grid, block by block
The rule that a public map carries no individual geometry SHALL hold for every public surface except
a report's map block whose editor switched the marks on (spec `reports-live-blocks`). Site results
blocks, grid, coverage and density views, the Data API and the MCP server SHALL keep the grid
whatever a report shows.

#### Scenario: A Site block of the same question
- **WHEN** a report shows the marks of a question and a Site results block shows the same question
- **THEN** the Site block's payload holds cells and no mark
