## Why

The start page shipped in `first-survey-onboarding` (#311) takes two clicks on desktop: a click
on a card only selects it and moves a detail block (paragraph, action button, "Always start this
way") under the row. The click changes nothing where the creator is looking. The day after
release a creator who had just signed up clicked the *Start from scratch* card six times
(`$dead_click` each time in PostHog, Replay Vision frustration 6/10) before finding the button
about 30 s later. Creating a survey is rare, so a "choose, then confirm" step and a remember
option on the page itself cost more than they give (#335).

## What Changes

- One click on a card performs the card's action. *Start from scratch* posts the blank-creation
  form (same endpoint, same geolocation-on-click, same double-submit guard). *Draft with AI*
  opens the create page with `?from=start`. *Connect your AI agent* stays inert.
- **BREAKING (UI)**: the detail block under the cards, the selected state, and the
  "Always start this way" checkbox are removed from the start page; the start page no longer
  writes `survey_start_default`. The longer explanation that lived in the detail block goes to
  the help article linked from the page header.
- The remembered default moves to a new personal **Preferences** page, `/editor/account/`,
  reached from the account menu in both base templates. It offers *Ask every time* /
  *Start from scratch* / *Draft with AI* and saves on submit. The start page header shows the
  current default with a link to Preferences instead of a "Clear" button.
- The dashboard's "+ New Survey" keeps routing by the default, and the ⋯ menu keeps
  "Start another way…" — unchanged.

## Capabilities

### New Capabilities
- `creator-preferences-page`: the personal Preferences page at `/editor/account/` and its
  account-menu entry; first setting is the default way to start a survey.

### Modified Capabilities
- `survey-start-chooser`: cards act on one click; "Always start this way" and the start page's
  "Clear" action leave the page; the remembered default is set from Preferences.

## Impact

- `survey/templates/editor/survey_start.html` (markup, CSS, inline script shrink),
  `survey/assets/js/survey_start.js` (unchanged contract; the card is now the submit target).
- `survey/editor_views.py`: `editor_survey_start` drops `remember`/`clear`;
  `editor_survey_create_blank` drops `remember`; new `editor_account_preferences` view.
- `survey/urls.py`: `editor/account/` route.
- Account menus in `editor/editor_base.html` (two) and `base.html`: "Preferences" entry.
- Help centre: `how-to/choose-how-to-start.md`, `start-here/create-a-survey.md`.
- Translations for new strings in all offered catalogs plus `ru`.
- No model or migration change: `CreatorPreferences.survey_start_default` stays as it is.
- `survey-start-chooser` exists only as a delta in the unarchived `first-survey-onboarding`
  change, so that change must be archived before this one.
