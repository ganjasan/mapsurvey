## ADDED Requirements

### Requirement: Budget block

The public results page SHALL offer a `budget` block for `budget` questions that renders the
mode's aggregate from `budget_stats`: Split — mean amount and share per item; Projects — share
of respondents per project with the fitting set marked. The block is server-rendered (no
script). An item with fewer than K respondents behind it (non-zero in Split, picked in Projects)
SHALL be masked the way a small choice bucket is. Individual allocations SHALL never be
published. A budget group's marks publish through the ordinary map blocks of its member
questions; a group block on the public page is a follow-up.

#### Scenario: Masked item

- **WHEN** K is 3 and only two respondents gave "Community voice" anything
- **THEN** that item's bar shows the masking note and the other items render

#### Scenario: Group marks publish as maps

- **WHEN** a budget group's bench question is added to the page
- **THEN** it becomes a `map` block, as any point question
