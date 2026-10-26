## ADDED Requirements

### Requirement: A hero is a changelog entry with a hero header
A changelog entry MAY declare `tier: hero`. A hero entry MUST have `kind: new`, a `link` URL
name and a `cta_label`, and MAY have `art` (a name the hero partial knows, `agent` at least),
`eyebrow`, `link_query`, `help` (a `HELP_URL` key), `chips` (`|`-separated prompts in which
`{survey}` stands for a survey name), `show_if` (comma-separated predicate names) and
`note_if` + `note`. The loader SHALL reject a hero with `kind: fixed`, without `link` or
`cta_label`, with an unknown `art`, with a predicate name missing from the audience registry,
or a `card` entry carrying `show_if`, `note_if` or `chips`, naming the file. Every hero's
`link` in the shipped directory SHALL resolve.

#### Scenario: A well-formed hero loads
- **WHEN** an entry declares `tier: hero`, `kind: new`, `link: editor_survey_start_agent`,
  `cta_label: Connect your assistant`, `art: agent`, `show_if: has_surveys,no_mcp_connection`
- **THEN** `changelog.entries()` holds it with `tier == 'hero'` and the parsed keys

#### Scenario: A hero without a call to action is rejected
- **WHEN** an entry declares `tier: hero` and no `cta_label`
- **THEN** loading raises an error naming the file

#### Scenario: An unknown predicate is rejected
- **WHEN** a hero declares `show_if: has_surveys,unicorns`
- **THEN** loading raises an error naming the file and the predicate

#### Scenario: A fix cannot be a hero
- **WHEN** an entry declares `kind: fixed` and `tier: hero`
- **THEN** loading raises an error naming the file

### Requirement: Audience predicates are a registry
The system SHALL hold the hero audience predicates in one Python registry, each a callable of
(user, active organization) returning a boolean: `has_surveys` (the workspace has at least one
survey outside the trash), `no_mcp_connection` (the user has no unrevoked token profile with
the `mcp` audience), `free_plan` (the workspace's entitlement lacks the `api` feature). A
predicate's result SHALL be computed at most once per request.

#### Scenario: Connection ends the audience
- **WHEN** a creator holds an unrevoked OAuth grant with the `mcp` audience
- **THEN** `no_mcp_connection` is false for them

#### Scenario: A revoked grant does not count
- **WHEN** the creator's only MCP grant is revoked
- **THEN** `no_mcp_connection` is true

#### Scenario: Trash does not count as a survey
- **WHEN** the workspace's only survey is in the trash
- **THEN** `has_surveys` is false

### Requirement: A hero is pending while unseen, within 30 days and in audience
A hero entry SHALL be *pending* for a creator when its id is newer than their
`changelog_seen`, its date is at most 30 days before today, every `show_if` predicate holds,
and `changelog_cards` is on. When several heroes are pending the newest SHALL be chosen.
Predicates SHALL be evaluated only when an unseen hero within its lifetime exists.

#### Scenario: Expired hero is not pending
- **WHEN** a hero dated 31 days ago is unseen by a creator in its audience
- **THEN** no hero is pending for them and the hero does not render as a small card either

#### Scenario: Audience fails
- **WHEN** a hero with `show_if: no_mcp_connection` is unseen by a creator who has an MCP
  connection
- **THEN** no hero is pending; a newer unseen `card` entry, if any, shows as a small card

#### Scenario: No predicate query outside the window
- **WHEN** a creator's watermark is already past every hero entry
- **THEN** resolving `whats_new` runs no audience query

### Requirement: The hero renders on the dashboard only, and suppresses the small card everywhere
The dashboard `/editor/` SHALL render a pending hero above the survey list: the plate (`art`
or `image`), the eyebrow, the title, the body, the chips, one primary call-to-action linking
to `link` with `link_query`, the "How it works" link when `help` resolves to a help page, the
`note` when `note_if` holds, a × and "Don't show these". While a hero is pending the system
SHALL render no small card on any page, and SHALL render the hero on no page but the
dashboard. The hero SHALL NOT render on respondent surfaces, for anonymous users, or when
`changelog_cards` is off.

#### Scenario: Dashboard shows the hero
- **WHEN** a creator with a pending hero opens `/editor/`
- **THEN** the response contains the hero with its title, the CTA linking to the resolved
  `link` plus `link_query`, and no small-card markup

#### Scenario: Editor page shows nothing while the hero is pending
- **WHEN** the same creator opens a survey editor page
- **THEN** the response contains neither the hero nor the small card

#### Scenario: Free workspace sees the note
- **WHEN** the hero declares `note_if: free_plan` and the active workspace is on Free
- **THEN** the hero shows the `note` line; on a Pro workspace it does not

### Requirement: Chips name the creator's own surveys
Each `{survey}` in a chip SHALL be replaced by a survey name of the active workspace —
published surveys first, newest first — one name per chip, cycling when there are fewer
surveys than chips. A chip whose placeholder cannot be filled SHALL be dropped. Chips SHALL
be plain text, escaped on render.

#### Scenario: Two surveys, three chips
- **WHEN** the workspace has published surveys "Park" and "Bikes" and the hero has three chips
  with `{survey}`
- **THEN** the chips read with "Park", "Bikes", "Park" in that order

#### Scenario: Survey name with markup
- **WHEN** a survey is named `<b>x</b>`
- **THEN** the chip renders the escaped text, not bold

### Requirement: Closing the hero covers everything and stays closed
×, the primary CTA and "Don't show these" on the hero SHALL move the watermark to the newest
entry id through the existing endpoints (`how` ∈ `close | cta`, or the cards switch), so no
small card follows on this or the next page. The CTA SHALL navigate without waiting for the
POST. Before the POST, the browser SHALL remember the closed entry id in `localStorage`; a
card or hero whose entry id equals the remembered id SHALL be hidden on render even when the
watermark has not moved, and the POST SHALL be retried then. The same guard SHALL apply to
the small card.

#### Scenario: CTA closes the hero
- **WHEN** a creator posts `how=cta` for the hero
- **THEN** `changelog_seen` equals the newest id, `changelog_card_clicked` (`target=cta`,
  `tier=hero`) and `changelog_card_dismissed` (`how=cta`, `tier=hero`) are emitted, and the
  next dashboard render has no hero and no small card

#### Scenario: Close that failed to persist
- **WHEN** the watermark POST fails and the creator opens the next editor page
- **THEN** the card markup carries the entry id and the page script hides it at once because
  the remembered id matches, instead of showing it again

### Requirement: Hero budget
The shipped `survey/changelog/` directory SHALL contain no two hero entries dated fewer than
14 days apart; `ChangelogEntriesTest` SHALL fail otherwise.

#### Scenario: Two heroes one week apart
- **WHEN** hero entries dated 2026-11-01 and 2026-11-05 are loaded by the budget test
- **THEN** the test fails naming both ids

### Requirement: The first hero sells the assistant to creators with surveys
The repository SHALL ship a hero entry dated the release day with `art: agent`, title "Edit
these surveys and read their responses from Claude or ChatGPT", a body about connecting once
and asking for a change, a summary or the share link, three chips with `{survey}`, `link:
editor_survey_start_agent` with `link_query: from=dashboard`, `cta_label: Connect your
assistant`, `help: mcp`, `show_if: has_surveys,no_mcp_connection`, `note_if: free_plan` and
`note: Part of Pro · connecting is free`.

#### Scenario: Creator with surveys and no connection
- **WHEN** a creator whose workspace has a published survey and who has no MCP connection
  opens the dashboard within 30 days of the entry date
- **THEN** the hero renders with a chip naming that survey and the CTA to
  `/editor/surveys/start/agent/?from=dashboard`

#### Scenario: Creator with an empty workspace
- **WHEN** a creator whose workspace has no surveys signs in
- **THEN** the start page they are sent to carries no hero, and the dashboard (`?dashboard=1`)
  shows no hero either

### Requirement: The agent page knows where the creator came from
`GET /editor/surveys/start/agent/` SHALL accept `from` ∈ `dashboard | help | connections`;
for `dashboard` the back link SHALL read "Dashboard" and lead to `/editor/`; otherwise the
back link stays "Ways to start". The value SHALL be exposed to the page script so the agent
events it already emits carry `from`; an unknown value SHALL be dropped.

#### Scenario: From the dashboard
- **WHEN** the page renders with `?from=dashboard`
- **THEN** the back link leads to `/editor/` and the page root carries `data-from="dashboard"`

#### Scenario: Unknown origin
- **WHEN** the page renders with `?from=<script>`
- **THEN** the response carries no `data-from` value and no echo of the parameter
