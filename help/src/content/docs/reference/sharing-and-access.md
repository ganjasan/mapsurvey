---
title: Sharing and access
description: What the Share page offers, who can open a survey in each status, and what the organisation and survey roles allow.
sidebar:
  order: 40
---

## The Share page

**Share** in the survey navigation opens the Share page. Until the survey is published it shows only a notice (the public link gives a 404 for a draft; a testing survey works only through its test link) and, for the owner, a **Publish — open for responses** button.

Once published, the page contains:

| Section | What it holds |
|---|---|
| **Survey link** | The direct link, `https://mapsurvey.org/surveys/<id>/`, with **Copy link** and **QR code** |
| **Results page** | The public results link once that page is published, or a **Review & publish the results page** button. See [Share results publicly](/how-to/share-results-publicly/) |
| **Embed on your site** | The iframe snippet, **Copy embed code** and the **Sites allowed to embed** list. See [Embed a survey](/how-to/embed-a-survey/) |
| **Track where responses come from** | Makes a tracking link per channel from a **Source**, **Medium** and **Campaign**. Responses arriving through it are tagged and compared under **Responses › Traffic Sources** |
| **Your Tracking Links** | The links made so far, each with copy, QR code and delete |

The survey navigation also has a **Share** menu with **Share link & tracking…**, **Copy results link** and, while testing, the test link.

## Who can open a survey

| Status | Anyone with the link | With the test link | Collaborators |
|---|---|---|---|
| Draft | No — "Survey unavailable" | No | Preview only |
| Testing | Only if no password is set; with a password, the password is asked | Yes, without the password | Yes |
| Published | Yes; the password is asked if one is set | — | Yes |
| Closed, Archived | No — "Survey Closed" | No | Can still read responses and export |

A respondent needs no account. **Visibility** (Private, Public, Demo) only decides whether the survey is listed on the landing page; it never blocks a link. A published survey held for content review shows the same "unavailable" page as an unknown link until it is released.

## Organisation roles

Every survey belongs to an organisation (your workspace). Members are managed under **Members** in the organisation menu; owners and admins can **Invite Member** by email.

| Role | Can |
|---|---|
| **Owner** | Everything, including **Plan & billing**, upgrading to Pro, and changing or removing other owners |
| **Admin** | Manage members (not owners), organisation settings, and every survey as a survey owner |
| **Editor** | Create their own surveys and work on the surveys they are added to as a collaborator; no automatic access to other members' surveys |
| **Viewer** | Read every survey of the organisation and its responses, and export |

## Survey roles (collaborators)

**Collaborators** in the survey's **Settings** adds a member of the organisation to one survey with a role. The effective role is the higher of the organisation role and the collaborator role.

| Role | Can |
|---|---|
| **owner** | Everything on the survey: publish, close, publish or discard unpublished changes, change settings, delete |
| **editor** | Edit the survey and start unpublished changes, configure sharing and embedding, read responses and export. Cannot publish |
| **viewer** | Read responses, use the Responses map and table, export. Cannot edit |

Collaborators added to a published survey are also recognised on its unpublished changes and its archived versions.

## Related

- [Survey settings](/reference/survey-settings/)
- [Embed a survey](/how-to/embed-a-survey/)
- [Share results publicly](/how-to/share-results-publicly/)
- [Exports](/reference/exports/)
