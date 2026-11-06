## ADDED Requirements

### Requirement: Responses opens a response named in the URL
The Responses page SHALL open a session's detail surface on load when `RESPONSES_V2` is on and
the URL carries `?session=<id>` without a `#thread-<id>` hash, through the same endpoint and
family check a row click uses. With `map=1` as well, the page SHALL open that
response's full-size map once the detail surface has rendered, if the response has geo answers.

#### Scenario: Link opens the drawer
- **WHEN** a creator loads Responses with `?session=42` where 42 is a session of the survey
- **THEN** the detail surface opens on session 42

#### Scenario: Link with map=1 opens the map too
- **WHEN** a creator loads Responses with `?session=42&map=1` and session 42 has a point answer
- **THEN** the detail surface opens on session 42 and its full-size map is shown

#### Scenario: Comment links keep their own handling
- **WHEN** a creator loads Responses with `?session=42#thread-7`
- **THEN** the comments deep link opens the drawer and scrolls to thread 7, and the page does not open the drawer a second time
