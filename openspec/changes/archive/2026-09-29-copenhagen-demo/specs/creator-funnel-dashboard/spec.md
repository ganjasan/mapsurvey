## MODIFIED Requirements

### Requirement: Demo opens reported as total plus authentication split

The dashboard SHALL report demo opens as a total derived from all non-deleted sessions on the demo
survey, excluding sessions tagged `sample`, and separately as anonymous versus signed-in counts derived
from recorded demo-open entries. The split SHALL state the date from which it has been recorded, and
SHALL NOT be presented as covering sessions that predate that date.

#### Scenario: Total covers full history

- **WHEN** the demo total is computed for a window predating the split's start
- **THEN** it counts the demo survey's non-deleted sessions in that window

#### Scenario: Sample sessions are not demo opens

- **WHEN** the demo survey holds sessions tagged `sample`
- **THEN** the demo total SHALL NOT count them

#### Scenario: The split is bounded by its start date

- **WHEN** the anonymous and signed-in counts are shown
- **THEN** the section states the date recording began, and does not attribute earlier sessions to
  either group

#### Scenario: The demo survey is identified

- **WHEN** the demo panel renders with a resolvable demo survey
- **THEN** it names the survey the numbers refer to

#### Scenario: The demo survey cannot be resolved

- **WHEN** the demo survey URL is unset or points at a survey that no longer exists
- **THEN** the demo stage renders as not configured and the rest of the dashboard renders normally
