## 1. Start page: one click

- [x] 1.1 `survey_start.html`: *Start from scratch* card becomes the submit `<button>` of the blank form (spans, not divs/h2); *Draft with AI* card becomes an `<a>` to `editor_survey_create?from=start` (a `div.disabled` without provider); agent card unchanged
- [x] 1.2 Remove `.start-detail`, `#start-lore`, selected-state CSS, "Always start this way", the fine print and the inline selection script; move the AI-provider sentence to the AI card's *who* line
- [x] 1.3 Header: "Your default: X · Change in Preferences" link instead of the Clear form
- [x] 1.4 `survey_start.js`: busy label goes into `[data-busy-target]` when the button has one
- [x] 1.6 Wizard card (the AI draft, renamed from "Draft with AI") first, badged "Best to start", accent border; without a provider it moves behind "from scratch"; same name in Preferences and "Your default"
- [x] 1.7 "Wizard" everywhere the creator meets the AI draft (brief panel, intercept, feedback strip, error copy, help, changelog); disclosure explains "The Wizard is an AI agent"; icon `fa-magic`
- [x] 1.5 `editor_survey_start` GET-only (`require_GET`), drop `ai`/`clear` branches; `editor_survey_create_blank` drops `remember`

## 1b. Dashboard (found in the same session)

- [x] 1b.1 Grid track `minmax(min(300px,100%),1fr)` / mobile `minmax(0,1fr)`, card `min-width:0`, `.card-name` `overflow-wrap:anywhere`; regression test

## 2. Preferences page

- [x] 2.1 `editor_account_preferences` view (`@login_required`, GET/POST, 400 on invalid, messages + PRG) and route `editor/account/` (`editor_account_preferences`)
- [x] 2.2 `editor/account_preferences.html` extending `editor_base.html`: radio group, AI option disabled without provider, Save
- [x] 2.3 "Preferences" entry above "What's new" in the three account menus (`editor_base.html` ×2, `base.html`)

## 3. Tests

- [x] 3.1 Update `first-survey-onboarding` tests that post `remember`/`action=clear`/`action=ai` to the start page
- [x] 3.2 Start page: blank card is a submit button of the blank form, AI card is a link with `from=start`, no "Always start this way", no detail block, disabled AI card has no link, POST → 405, default shown with Preferences link
- [x] 3.3 Blank endpoint ignores `remember=1`
- [x] 3.4 Preferences: renders current value, no row = ask and no write, save ai/blank/'' with redirect, invalid → 400 unchanged, viewer can save, anonymous → login, menu link on dashboard and editor

## 4. Docs and strings

- [x] 4.1 Help: rewrite `how-to/choose-how-to-start.md` steps 2–4 and `start-here/create-a-survey.md` step 2 for one click and Preferences; point the 2026-10-14 changelog entry at Preferences
- [x] 4.2 CLAUDE.md: note Preferences page where the start chooser is described (if mentioned)
- [x] 4.3 New creator strings in all offered catalogs plus `ru`; compile; run the catalog guard tests

## 5. Verify

- [x] 5.1 Run the start-page/onboarding tests and the full `survey` suite once
- [x] 5.2 Click through on the dev server: desktop and phone width, blank card one click, AI card one click, Preferences save → dashboard button routes
- [ ] 5.3 Archive `first-survey-onboarding` before archiving this change (its delta holds `survey-start-chooser`)
