---
title: Sites
description: One public site for an engagement — what the project is about, the timeline, the surveys residents can take part in — on an address that stays the same from the first pilot to the final plan.
sidebar:
  order: 79
---

A public engagement is longer than one survey: a pilot, the main survey, a round of feedback on the proposal, open-house events. A **site** is the one address residents need for all of it. Put it on flyers, posters and QR codes; it stays the same while the surveys behind it open and close.

Sites are part of **Pro**. A workspace on the Pro trial can create one.

## Create a site

1. Open **Sites** in the sidebar and press **New site**. The site opens in the builder as a draft, with its title selected.
2. Type the title over it, for example *Riverside Park plan*. Until you publish, the site's address follows the title.
3. Click the line under the title and write a summary of one or two sentences; press **Add a cover picture** at the top right of the title area, or drop a picture onto it. The summary is also what people see when the link is shared.

## How the builder works

The middle of the builder is the site itself, as residents will see it.

- **Click any text to change it** — the title, the summary, a heading, a paragraph, a caption, a button label. Select words for bold, italic, links and lists.
- **Fill a block in where it is.** Drop a picture, a GeoJSON file or documents onto the block (or click to choose them), paste a video or button link into the field under it, type the questions of an FAQ and the phases of a timeline straight into the rows, set an event's date, time and place above its card, pick the survey of a card or the question of a results block from the list in the block.
- **Click a block** to see its other settings on the right — the finer points: picture description, button style, map colour and style, chart type, time zone and seats of an event. With nothing selected, the right side holds the site settings: the cover picture's description, address, language, visibility and the surveys on the site.
- **Point between two blocks** and press **+** to add a block there, or use **Add block** at the bottom.
- **Point at a block** for its toolbar: drag to move, up and down, duplicate, settings, delete. The list on the left shows every block; click one to jump to it, or drag to reorder.
- **Everything saves by itself.** The top bar says *Saving…* and *All changes saved*. A block you have not finished (a picture without the picture, an event without a time) stays in the builder and is not shown on the site until it is complete.
- **Accessibility notes** (violet, with the accessibility icon) point at what a screen reader or keyboard user would trip over: a picture without a description, a small heading before any larger one, a link that only says “here”. The Publish panel lists them; they never stop you publishing.
- The **phone** button at the top shows the site at phone width.
- **Page width** (site settings) sets how wide the column is on a computer: *Narrow* for reading, *Standard*, or *Wide* for plans and drawings. Pictures, maps and videos can also go **Full width** — edge to edge of the page — in their own settings.

## Add blocks

Press **+** or **Add block** and choose what to add:

- **Heading** — a section title on its own: large, medium or small (Settings, **Size**). Use it to open a part of the site, or for a subheading between blocks.
- **Text** — formatted text: what the project is, why residents are asked, what happens with their answers. The toolbar offers **Heading** and **Subheading** inside the text.
- **FAQ** — questions and answers that open on a tap.
- **Timeline** — the phases of the engagement with their dates. Press **Now** on the phase you are in; earlier phases show as done.
- **Image** — a picture with a description for screen readers and an optional caption.
- **Video** — a YouTube or Vimeo link.
- **Survey card** — one of your surveys. The card follows the survey: *Open* with a **Take part** button, *Opens on …* before its period starts, *Coming soon* while it is a draft, and *Closed* with a link to its [public results](/how-to/share-results-publicly/) once you publish them.
- **Button** — a link to anything else: the draft plan, the council's website, an event sign-up.
- **Contacts** — who runs the project and how to reach them: add people (name, role, e-mail, phone) right in the block, the address and opening hours in its settings.
- **Documents** — files to download: the input summary, the open-house boards, the draft plan. PDF, Word, Excel, PowerPoint, OpenDocument, CSV or plain text, up to 25 MB each and 20 per block. Each file gets a title (the file name to start with) that you can change on the block; **×** takes one off.
- **Results** — what residents said in a round: a chart of a choice, rating or number question, or a map (markers, heatmap or clusters) of a map question, from any survey of your workspace. Answers are counted as on the survey's [public results page](/how-to/share-results-publicly/): only reviewed, non-deleted responses, small groups masked, written answers never shown. The block updates by itself as answers come in.
- **Map** — the project area on a map. Upload a GeoJSON file with the boundary, a route or a few points (up to 1 MB; export it from QGIS or draw it on [geojson.io](https://geojson.io)), pick a colour and one of your [map styles](/how-to/map-styles/). A shape's `name` shows when someone points at it.

Every block can have a **heading** above it — or none: leave *Heading (optional)* empty and the block starts with its content. A heading also becomes a link in the menu at the top of the site; untick **Show the heading in the menu at the top** in the block's settings to keep it out. The menu appears once it has two links. Drag blocks by the handle to change their order.

## Events and registration

The **Event** block announces an open house, a walk or a workshop: date, start and end time in the event's time zone, the place (with an optional map link), a few words about it, and an optional number of seats.

While **Registration open** is ticked and the event has not ended, the block carries a short form: name, email and a box the resident ticks to agree. They get an email with the details, a calendar file and a link to cancel; a cancelled registration frees its seat. The same email registers only once.

Under the event in the builder, **Attendee list** shows who registered, with a CSV download and **Remove** / **Remove all**. Names and emails are for this event only: Mapsurvey deletes them automatically **30 days after the event** — the form says so to every resident. Owners, admins and editors of the workspace see the list; viewers do not.

## Surveys on the site

**Surveys on this site** lists the surveys the site shows. Add one there or straight from a survey card. A survey can be on any number of sites — the same city-wide survey on two neighbourhood sites, for example. Removing a survey from the site removes its cards.

## Start from an earlier site

**Duplicate** on the Sites list (or **Duplicate site** in the site settings) makes an unpublished copy to start the next engagement from: the same blocks, files, surveys and settings, a new address. Event registrations are never copied.

## Publish

Press **Publish** in the top bar. The panel that opens shows the address — `mapsurvey.org/p/<address>/`, with a copy button — a switch for search engines and the QR code to download; **Publish now** puts the site live. Change the address (site settings, **Address**) before you print it: changing it later breaks the links already out there.

- **Public** sites may be listed by search engines.
- **Unlisted** sites are reachable only by people who have the link.

Until you publish, only members of your workspace can open the site; they see a *Draft* banner. **Unpublish** takes the site offline at any time.

To show the draft to a client before it goes live, copy the link under **Share for review** in the Publish panel. Anyone with it sees the draft read-only for 14 days, without an account; event registration stays closed. **New link** stops every link you sent before.

## If your Pro plan ends

A published site stays online, so the QR codes you printed keep working. You can still unpublish or delete it, but not edit it, until the workspace is on Pro again.
