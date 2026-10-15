## Context

`first-survey-onboarding` (#311) built `/editor/surveys/start/` as a "life-path" screen: on
≥768px a click selects a card and JS moves that card's `.start-detail` (long paragraph, action
form, "Always start this way" checkbox, fine print) into `#start-lore` under the row; on phones
every card shows its detail block inline. Only the button inside the detail block acts. The
remembered default (`CreatorPreferences.survey_start_default`: `''`/`blank`/`ai`) is written
by the `remember=1` checkbox on either form and cleared by an `action=clear` POST on the same
page. The dashboard reads it through the `survey_start` context processor.

Evidence for the change is in #335: dead clicks on the card on the first day, one frustration
score of 6/10 directly attributable to it.

## Goals / Non-Goals

**Goals:**
- One click on an actionable card does the action, on every viewport.
- The start page carries only what a creator needs to choose: label, picture, what happens,
  who it is for.
- The default way to start keeps working for the dashboard, set from a stable personal place.

**Non-Goals:**
- No change to blank-survey creation itself, the map-start chain, the create page, or the
  dashboard's routing by default.
- No model change. No other preferences move to the new page in this change (the editor
  confirmation toggle and the changelog switch stay where they are).
- The 403 on dismissing the "What's new" card seen in the same sessions is a separate defect.

## Decisions

### D1. The card is the button
*Start from scratch*: the whole card is the `<button type="submit">` of the existing
`form[data-survey-start="blank"]`. A `<button>` admits phrasing content only, so the card's
parts become `<span>`s styled as blocks (the title keeps its look via a class, not an `<h2>`);
the AI card, a link, uses the same spans so both cards share one stylesheet. That keeps
`SurveyStart.bindBlankForm` untouched: it already intercepts submit, asks for geolocation tied
to the click, disables the button and shows the busy label, then submits once. The busy label
goes into a dedicated `.start-busy` line inside the card, so the card's text is not replaced
wholesale; `survey_start.js` sets `textContent` on the button today, so it gains one rule: if
the button holds an element `[data-busy-target]`, write the label there instead.

*Draft with AI*: the card is a plain `<a href="{% url 'editor_survey_create' %}?from=start">`.
It was a POST only to carry `remember=1`; with remembering gone a GET link is correct (it
creates nothing) and keeps middle-click / open-in-new-tab.

*Connect your AI agent*: unchanged `div` with `aria-disabled`, as before.

When AI is not configured, the AI card renders as a `div.disabled` with the existing "Not
available on this server" line — no link.

*Alternative considered*: keep the selection and auto-scroll to the detail block. Rejected —
still two clicks for a rare action, and the scroll is itself disorienting.

### D2. Remove the detail block, keep one line of help
The `.start-detail` blocks, `#start-lore`, the selected styles (`.selected`, `.start-check`,
the arrow `::after`) and the inline selection script go. The long paragraphs were the only
place that said "the map opens where you are" and "your description goes to an AI provider";
the first already sits in the card's *what* line, the second moves to the AI card's *who*
line ("Your description goes to an AI provider; answers never do."), and both are in the help
article that the header already links ("How this works").

### D3. Preferences page at `/editor/account/`
A small page, `editor/account_preferences.html` extending `editor_base.html` (the same as the
MCP page beside it), view `editor_account_preferences` (`@login_required`, GET/POST):
one form, a radio group *Ask every time* / *Start from scratch* / *Draft with AI* bound to
`survey_start_default`, a Save button, a success message via `django.contrib.messages`,
redirect back (PRG). Invalid values → 400. *Draft with AI* is shown disabled with the same
"Not available on this server" note when no provider is configured, but a stored `ai` is
displayed as selected, not silently reset.

It is a personal page, not a workspace one, so it needs only a login, not an org role: a
viewer can store a default too (the dashboard hides "+ New Survey" from viewers anyway).

URL `editor/account/` is the natural parent of `editor/account/mcp/`. The name "Preferences"
matches `CreatorPreferences` and leaves room for other personal settings later.

*Alternative considered*: workspace Settings. Rejected — the default is per user, and putting
it on a page every member shares would suggest it applies to all of them.

### D4. Account menu entry
"Preferences" (`fa-sliders-h`) goes in all three account menus (two in `editor_base.html`,
one in `base.html` — the dashboard extends `base.html`) directly above "What's new".

### D5. Start page header
When a default is set, the header says "Your default: **X** · Change in Preferences" (a link),
replacing the "Clear" form. The `action=clear` and `action=ai` POST branches of
`editor_survey_start` are removed; the view becomes GET-only (`require_GET`). The `remember`
branch of `editor_survey_create_blank` is removed; a stray `remember=1` from an old open tab is
ignored, not an error.

## Risks / Trade-offs

- [One click now creates a survey; an accidental click leaves an "Untitled survey"] → The
  same was already true of the dashboard's blank default; the double-submit guard stays, and
  an untitled empty survey is cheap to delete. Accepted.
- [An old tab of the start page posts `action=ai`/`clear` after deploy] → the view answers 405;
  the creator reloads. Rare and harmless.
- [Creators who learned "Always start this way" from the help or changelog] → the help article
  is rewritten in this change, and the one sentence of the 2026-10-14 changelog entry that told
  creators to tick the box now points to Preferences (same entry id, so seen-state is kept; most
  creators have not seen it yet, and a card must not teach a control that no longer exists).

## Migration Plan

No data migration. Deploy is a template/view change; rollback is a revert.
`first-survey-onboarding` must be archived before this change, because `survey-start-chooser`
exists only as its delta.
