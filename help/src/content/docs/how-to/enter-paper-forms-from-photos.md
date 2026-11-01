---
title: Enter paper forms from photos
description: Photograph or scan filled paper forms, let Mapsurvey read the answers, check them beside the picture and store each form as a paper response.
sidebar:
  order: 76
---

You end up with every filled form stored as a paper response — read from a photo, checked by you, without typing the answers in.

## Before you start

- Your organisation is on **Pro**, and you have the **editor** role or higher on the survey.
- The forms were printed with **[Print a paper form](/how-to/print-a-paper-form/)**. Every page carries a code; it is how a photo finds its survey, version and page. A form printed any other way cannot be read.
- Best: you printed **numbered copies**. Each copy carries its own number on every page, so photos and scans of a whole stack sort themselves, in any order. With **one copy to photocopy**, every photocopy looks the same, so you tell Mapsurvey which photos belong together (see below).
- You have the forms as photos (any phone) or scans (a flatbed, an office copier, a PDF).

## Photograph the forms

- One page per photo, the **whole page** in the frame, flat on a table, in even light. Keep the two **QR codes at the bottom** in the picture; one is enough if a thumb covers the other. On a map page keep all **four black corner squares** in the picture: they are what puts the marks on the map.
- Order does not matter. Numbered copies sort themselves; for a response you open yourself, every page finds its place by the page number printed on it.
- A scanner is fine too: a PDF of the stack, or one image per page.

## Steps

1. Open the survey's **Responses** page, open the arrow next to **Enter a response** and choose **From photos of paper forms**. The **Paper responses** page opens. It shows how many numbered copies were printed and how many have come back.
2. Add the photos, one of two ways:
   - **Upload a stack.** Drop the files on the page, or choose them. Dozens at once is fine, and so is adding a few more while the first ones are being read. A multi-page PDF is split into pages for you. Pages of numbered copies go to their copy's response, whatever order they came in. With one copy to photocopy, upload **one PDF per filled form**: each PDF becomes one response.
   - **New response.** Press it, then drop the photos or the PDF of **one** form into its card. Use this for a single form, or for photocopied forms photographed page by page.
   On a phone, press **Take photo** to shoot pages straight from the page — one page per shot, tap again for the next.
3. Wait for the cards to fill in. Each response shows a box per page: read, **to check** (the reader was unsure about something), **reading…**, or **not photographed**.
4. Press **Check** on a response, or the **Check Copy N** button at the top, which always names the next one ready. The survey opens page by page of the printed form, with the **photo of the page on the left** and the questions printed on it on the right, already filled in. Fields the reader was unsure about are marked in amber; fields it saw left blank are grey.
5. Check each page against the photo, correct what is wrong, press **Next**. The page boxes at the top jump to any page. On the last page press **Finish**: the form is stored as a paper response and its photos are deleted. **Check next** opens the following one.

## When a photo is missing or in the wrong place

- **A page was not photographed.** The check says so where the photo would be. Press **Take photo** or **choose files** right there; the page is read and the fields fill in. You can also fill that page by hand, or press **Next** to leave it blank.
- **The same page twice.** The later photo wins. The earlier one is kept under the response; **Use the earlier photo** swaps them back.
- **A photo dropped into the wrong card.** A numbered page always goes to its own copy, and the card you dropped it on says where it went.
- **Set aside**, on the Paper responses page. A photo lands here when nothing can tell whose it is: a single photo of a photocopied form, a page whose code cannot be read, a page of a response already stored, or a page of another survey. Each one says why. Pick the response and page number and press **Attach**, or remove it.

## What the reader is good and bad at

- Ticks, crosses and filled boxes: good. A faint pencil mark or a box on a fold: it will say so and ask you to check.
- Handwritten text: transcribed as written, in its language. Expect to fix a word now and then; the field is marked amber when the reader was unsure.
- Numbers in boxes and ratings: good.
- **Marks on the map** are read too. A dot, a line or an outlined area drawn on the printed map, with its letter and number written next to it (A1, B2), appears as a pin on the map of the check where the respondent drew it. The map page of the check looks like the paper: the printed frame as a live map, then the same table of marks with the same rows and columns, filled with what the respondent wrote in each row. Click a row and the photo scrolls to its mark; drag a pin to correct a place; a row that is empty on paper offers **place it on the map** in case the reader missed one. For this the photo must show the **small black squares beside the map** (six, printed in the margins next to its corners and halfway down its sides) or the **four corner squares of the page**: they tell Mapsurvey how the paper lies in the picture, and a page that is bent or photographed at an angle is read as it lies. The more of them in the shot, the better; a photo of the map alone is fine as long as the squares beside it are in. Without any of them the map frame itself is used, less precisely; a photo that shows none comes back with the map questions empty, and you place the marks by hand. Forms printed before November 2026 have only the page corners.

## Where things go

- A paper response is stored exactly like a response typed in by hand: source **Paper form**, your name as the person who entered it. The response details link back to it as **Copy 37** (or **Response 4** for a form without a copy number), and exports carry the copy number in the `paper_copy` column, so you can find the paper original.
- Photos are kept only until the response is stored, and at most 30 days. **Delete** on a response you do not want removes it with its photos; its copy number can be uploaded again. A response nobody touches for 30 days is deleted the same way.
- Each page is read by the same AI that drafts surveys; the page image is sent to the provider for the duration of the reading. The codes are read on our server, not by the AI. See the [trust page](https://mapsurvey.org/trust/).
