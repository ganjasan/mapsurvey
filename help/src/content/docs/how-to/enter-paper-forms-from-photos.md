---
title: Enter paper forms from photos
description: Photograph or scan filled paper forms, let Mapsurvey read the answers, check them beside the picture and store each sheet as a paper response.
sidebar:
  order: 76
---

You end up with every filled sheet stored as a paper response — read from a photo, checked by you, without typing the answers in.

## Before you start

- Your organisation is on **Pro**, and you have the **editor** role or higher on the survey.
- The sheets were printed with **[Print a paper form](/how-to/print-a-paper-form/)**. Every page of that form carries a code; it is how a photo finds its survey, version and page. A form printed any other way cannot be read.
- You have the sheets as photos (any phone) or scans (a flatbed, an office copier, a multi-page PDF).

## Photograph the sheets

- One page per photo, the **whole page** in the frame, flat on a table, in even light. Make sure all **four black corner squares** are in the picture.
- Shoot the pages of one sheet **in order** — page 1, page 2, page 3 — then the next sheet. That order is how pages are grouped into sheets.
- A scanner is fine too: one PDF with all the pages in order, or one image per page.

## Steps

1. Open the survey's **Responses** page, open the arrow next to **Enter a response** and choose **From photos**.
2. Press **New batch**.
3. Drop the files on the page, or choose them. Dozens at once is fine; so is adding a few more while the first ones are being read. A multi-page PDF is split into pages for you.
4. Wait for the list to settle. Every sheet shows where it got to:
   - **N fields to check** — read; the number says how many answers the reader was unsure about.
   - **page 2 not uploaded** — a page is missing; photograph it and add it, or review what there is.
   - **page 2 twice — duplicate?** — the same page came in twice; remove one with the × on its thumbnail.
   - **Not recognised**, at the bottom — no code could be read on the page, or it belongs to another survey. Pick the printed form and page number and press **Assign**, or remove it.
5. Press **Review** on a sheet. The survey opens page by page as in [Enter responses for others](/how-to/enter-responses-for-others/), with the answers already filled in and the **photo of the page beside it**. Fields the reader was unsure about are marked in amber; fields it saw left blank are grey.
6. Check each page against the photo, correct what is wrong, press **Next**. On the last page press **Finish**: the sheet is stored as a paper response and its photos are deleted. **Next sheet** opens the following one.

If pages were grouped wrongly, drag a thumbnail from one sheet to another, or onto the dashed box to start a new sheet.

## What the reader is good and bad at

- Ticks, crosses and filled boxes: good. A faint pencil mark or a box on a fold: it will say so and ask you to check.
- Handwritten text: transcribed as written, in its language. Expect to fix a word now and then; the field is marked amber when the reader was unsure.
- Numbers in boxes and ratings: good.
- **Marks on the map are not read yet.** A sheet with a map page comes back with its map questions empty; put the marks on the map yourself while the photo is open (the **Map** button swaps the photo for the map on map pages).

## Where things go

- A sheet is stored exactly like a response typed in by hand: source **Paper form**, your name as the person who entered it, the sheet and batch number in the response details and in exports.
- Photos are kept only until the sheet is entered or skipped, and at most 30 days; a batch nobody touches for 30 days is closed and its photos deleted.
- Each page is read by the same AI that drafts surveys; the page image is sent to the provider for the duration of the reading. See the [trust page](https://mapsurvey.org/trust/).
