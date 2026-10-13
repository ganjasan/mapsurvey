---
title: Survey settings
description: Every survey-level setting — name, languages, visibility, what happens after the last page, map defaults, style, password and test access — and the survey's status lifecycle.
sidebar:
  order: 30
---

Survey settings live under **Settings** in the survey's navigation. Most of them save when you press **Save Settings**; the map position and the thanks page save automatically.

## General

| Setting | What it does |
|---|---|
| **Survey name** | The title respondents see. Any language; it must contain at least one letter or digit |
| **After the last page** | **Show the thank-you page** (default) or **Open a web address**. The address must be a full `http://` or `https://` link; anything else is refused. Inside an embedded survey the respondent stays on the thanks page and gets a **Continue** button to that address instead |
| **Available languages** | The languages the survey is offered in. A survey with more than one language shows a language picker before the first section — see [Translate a survey](/how-to/translate-a-survey/) |
| **Visibility** | **Private** (default): reachable only by its link. **Public**: also listed on the mapsurvey.org landing page once published. **Demo**: listed like Public and shown first in the listing; meant for the demonstration surveys Mapsurvey itself runs. Visibility never restricts who can open the link — status and password do that |
| **Cover image** | A picture shown on the survey card and listing |
| **Base maps** and **Default base map** | Which of **Streets**, **Satellite** and **Topo** respondents can switch between, and which one opens first |

## Style

| Setting | What it does |
|---|---|
| **Rating questions** | The default look of rating questions: **Compact scale**, **Labeled list** or **Stars**. A question can override it with its own **Display as** |
| **Custom accent color** and **Accent color** | Colours the survey's buttons and the form-page tint. Off = platform default |
| **Show the "Made with Mapsurvey" badge** | The badge on the survey, thanks page and public results. The switch works only on a Pro organisation; on Free it is shown but disabled — see [Plans and billing](/reference/plans-and-billing/) |

## Default map position

Drag and zoom the map so the pin marks where respondents start; the centre and zoom save automatically. Sections can override the position individually. **Auto-center on respondent's location** opens the map on the respondent's browser location when they first enter (they are asked for permission).

## Thanks page

The last screen respondents see. **Message** is written in a text editor, per language, and replaces the default "Thank you! Your responses have been recorded." A **Show a “See the results” button** switch links to the public results page once that page is published. Every thanks page ends with a share action and, on Free, the "Made with Mapsurvey" link.

## Collaborators

Members of your organisation who can work on this survey, each with a role of **owner**, **editor** or **viewer**. See [Sharing and access](/reference/sharing-and-access/).

## Password & Test Access

| Setting | What it does |
|---|---|
| **Password** | At least 4 characters. A published survey with a password asks every respondent for it before the first section. **Remove Password** turns it off |
| **Test Link** | Shown while the survey is in **Testing**. The link carries a token that opens the survey without the password; **Regenerate Token** invalidates links already sent |

## Embedding

**Sites allowed to embed** is on the **Share** page, not in Settings — see [Embed a survey](/how-to/embed-a-survey/).

## Status lifecycle

The survey's status is shown next to its name and changed from the publishing controls on the **Survey** page.

| Status | Who can open the link | Typical use |
|---|---|---|
| **Draft** | Only you, in **Preview**. Anyone else gets a "Survey unavailable" page | Building |
| **Testing** | Anyone with the **Test Link**; without it, anyone if no password is set, otherwise the password is required | Trying it yourself and with colleagues. Test responses can be deleted when you publish |
| **Published** | Anyone with the link (password first, if set). Also listed on the landing page if **Visibility** is Public | Collecting responses |
| **Closed** | Nobody — visitors see "This survey is no longer accepting responses" | Done collecting; responses and exports stay available |
| **Archived** | Nobody | Put away; cannot be reopened |

Transitions: Draft → **Move to Testing** or **Publish — open for responses**; Testing → **Back to Draft** or Publish; Published → **Close survey**, or **Back to Draft** while nothing has been collected; Closed → **Reopen survey**, **Archive**, or Back to Draft while nothing has been collected.

Once a survey is published, changing wording, help text, translations, added options and map or display settings happens in place. Adding, removing or reordering questions and sections, or changing a question's type, happens in **Unpublished changes** and goes live when the owner presses **Publish changes** — see [Edit a published survey](/how-to/edit-a-published-survey/).

## Public results page

A separate page under the **Public results** tab, with its own visibility (**Public** or **Unlisted**), its own publish switch and its own settings. See [Share results publicly](/how-to/share-results-publicly/).

## Related

- [Sharing and access](/reference/sharing-and-access/)
- [Translate a survey](/how-to/translate-a-survey/)
- [Edit a published survey](/how-to/edit-a-published-survey/)
