## ADDED Requirements

### Requirement: Lessons learned callout

A story body MAY contain one "Lessons learned" callout (`<aside class="sd-lessons">`). The callout
SHALL look the same in every story: the lessons-learned mark, the heading "Lessons learned", and
numbered lessons. Each lesson MAY end with an "In Mapsurvey" line naming what the product offers
for it, tagged Available, Built for <customer>, or Not yet; a Not yet line SHALL use the dashed
mark so a gap is never presented as a feature.

#### Scenario: Story with lessons
- **WHEN** a story body contains the callout
- **THEN** the story page renders it with the mark, numbered lessons and their In Mapsurvey lines

### Requirement: Lessons badge on the story card

A story card SHALL show a "Lessons learned" badge on its cover when the story body contains the
callout, and SHALL NOT show it otherwise.

#### Scenario: Card of a story with lessons
- **WHEN** the landing or `/stories/` lists a published story whose body contains the callout
- **THEN** its card shows the "Lessons learned" badge

#### Scenario: Card of a story without lessons
- **WHEN** a listed story's body has no callout
- **THEN** its card shows no badge
