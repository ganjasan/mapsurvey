---
title: Create a survey
description: Sign in, create the "Safe crossings" survey, frame its map and understand the editor's three panels.
sidebar:
  order: 1
---

By the end of this page you have an empty survey called "Safe crossings", its map centred on the street you care about, and a first section ready for questions.

## Sign in and open the dashboard

1. Go to [mapsurvey.org](https://mapsurvey.org/) and sign in. If you have no account yet, sign up with your email address; the free tier has no limit on surveys or responses. Signing up signs you straight in. Confirm the address from the email we send within 24 hours: until then you can build but not publish, and after 24 hours the sign-in page asks you to open the link first.
2. After signing in you land on the **Dashboard**, which lists your surveys. On a brand-new account Mapsurvey skips the empty dashboard and opens the **How do you want to start?** page for you; the **Skip to dashboard →** link takes you back if you want to look around first.

## Create the survey

1. Click **New Survey**. The page offers three ways to begin: **Survey wizard**, **Start from scratch**, and **Connect your AI agent** (not available yet). See [Choose how to start a survey](/how-to/choose-how-to-start/) for the differences.
2. Click the **Start from scratch** card. If your browser asks whether Mapsurvey may use your location, allowing it opens the map on your city; declining is fine, you frame the map in the next step either way.
3. The editor opens with a survey called **Untitled survey** and one empty section. Click the name in the header, type `Safe crossings` and press Enter. The name is shown to respondents, so keep it short and plain.
<!-- screenshot: the start page with its three cards -->

The survey runs in your interface language; you can add languages later, see [Translate a survey](/how-to/translate-a-survey/). The **Survey wizard** card drafts sections and questions from a written brief, which is useful once you know what a good survey looks like.

## Find your way around the editor

The editor has three columns:

- **Left**: the list of sections. A section is one page of the survey. Every new survey starts with one section; **New Section** adds more, and you reorder them by dragging.
- **Centre**: the selected section's settings and its questions. **New Question** opens the question dialog.
- **Right**: the **Live preview**, which renders the section exactly as respondents will see it and refreshes after every change.

Changes save as you type; the editor shows **All changes saved** when it is done. There is no save button for the survey as a whole.

<!-- screenshot: the editor with the sections list, section form and live preview labelled -->

## Set up the first section

1. In the centre panel, give the section a **Title**, for example `Crossings on Main Street`, and a short **Subheading** that tells respondents what to do.
2. Leave **Layout** on **Map**. The **Form** layout is a classic full-width page with no map, used for welcome text or demographics; **Picture** puts the questions beside a picture instead of the map. Map questions cannot live in either; see [Lay out a section](/how-to/lay-out-a-section/).
3. Click **Map Position**. In the picker, drag and zoom until the view shows the street at a scale where individual crossings are visible, or search for the place. This framing is exactly what respondents see when they open the survey, and it is also where you set the survey-wide map: untick **Inherit position (don't override)** only when this section needs a view of its own. Close the picker; the preview updates.
<!-- screenshot: the Map Position picker with the pin on a street and the base map picker open -->
4. If this section needs a different base map from the rest of the survey, pick one under **Override basemap** in the same picker.

## Check the survey-wide settings

Open **Survey settings** from the editor. Three things are worth checking now:

- **Default Map Position** and the base map list (**Base maps**, **Default base map**) set what every section inherits.
- **Visibility** controls whether the survey is listed in Mapsurvey's public gallery. It does not control who can open the link; a **Private** survey still opens for anyone who has its address once it is published. See [Sharing and access](/reference/sharing-and-access/).
- **After the last page** decides whether respondents see the built-in thank-you page or are sent to a web address of yours.

The full list is in [Survey settings](/reference/survey-settings/).

## Next

[Add a map question](/start-here/add-a-map-question/) — the question that collects the pins.
