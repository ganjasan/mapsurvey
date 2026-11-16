---
title: Share results publicly
description: Publish a page of charts and maps at a short address so respondents and the public can see what others said.
sidebar:
  order: 80
---

You end up with a public results page at `https://mapsurvey.org/r/<slug>/` showing aggregated answers — never individual ones — that you can link from the thanks page, a newsletter or a council website.

## Before you start

- The survey is **Published**. A draft survey's results page cannot be published.
- Decide what the public should see. Text answers are never shown; choice, rating, number, range and thumbs questions become charts; map questions become maps; **Objects on the map** questions become per-object totals.

## Steps

1. Open the survey and choose the **Public results** tab. Mapsurvey has already drafted a page from your questions, one block per publishable question.
   <!-- screenshot: the Public results editor with the block list and the preview -->
2. Arrange the blocks: drag to reorder, switch on **Hidden** for the ones you do not want, and press **Add block** to add a **Text block**, an **Image** or **Question results…** for a question that is not there yet.
3. Open a map block's **Block settings** and choose its **Point popup fields** — the sub-questions a visitor sees summarised when they click a square of the map. Free-text sub-questions cannot be shown. The public map never shows a respondent's own point, line or area: it shows squares coloured by how many respondents marked them, and hides any square with fewer respondents than the k-anonymity threshold — a single pin at a front door can tell neighbours who answered and what they said. The exact points stay in **Responses** and in the export.
4. Under **Page settings**, choose:
   - **Visibility**: **Public** is indexed by search engines and can be listed; **Unlisted** opens only by direct link and is not indexed.
   - **Data mode**: live data, or **Freeze snapshot** to publish a fixed copy. A frozen page keeps showing the snapshot until you press **Update snapshot** or **Back to live**.
   - **k-anonymity threshold**: groups smaller than this number are masked as "<K" on every chart and map. The default is 3; set it to 1 to switch masking off.
   - **Show response counter** and **Show “Take the survey” CTA** (the button shows only while the survey is open).
5. Press **Publish page**. The address is shown next to **Public URL**; **Copy public link** copies it, and the same link appears under **Results page** on the Share page.
6. To show the page to respondents after they finish, switch on **Show a “See the results” button** on the thanks page.

## Tell it as a story

The page is read top to bottom like an article, so write it like one. Under **Add block**, beside the results of a question, there are blocks you write yourself:

- **Heading** starts a section.
- **Text** is a paragraph, a list or a few of them, with bold, italics and links.
- **Image** is a picture with a caption — a photo, or a chart or map you made elsewhere.
- **Key numbers** is a strip of figures with a word under each. Enter one per line as `447 | residents answered`. You type these numbers; they do not change when new answers arrive.
- **Quotes** shows what people wrote, one per line, with an optional source after ` | `: `Give us the bridge back. | Pin: needs attention`. A quote is published exactly as you enter it, so leave out anything that names a person.

Blocks that follow the answers:

- **Cross-tab** puts two questions against each other — transport by age, say: how many people gave each pair of answers, among those who answered both. Pick the question for the rows and the one for the columns when you add it.
- **Engagement** shows how many people opened the survey, answered and finished, and how that went over time.
- A **map** block shows squares that count respondents. Switch on **Show the marks themselves** in the block's settings to show every place, line or area as it was drawn instead. A mark can point at someone's home, so decide whether that is right for your survey; the default stays the squares.
- **Numbers in the text** can follow the answers too. Write `{responses}` in a text, a key number or the opening paragraph and the page fills in how many people answered; `{opened}` and `{finished}` are the other two steps, `{marks:CODE}` the marks placed on a map question and `{respondents:CODE}` the people who answered a question, CODE being the question's code. A frozen page keeps the numbers of the day it was frozen. A count smaller than the privacy threshold reads "<3".

Set a block's **Width** to *Half width* to put two blocks side by side on a wide screen; on a phone they stack. Under **Page settings → Opening** add a line above the title and an opening paragraph.

All reports of the workspace are on the **Reports** page of the sidebar. **New report** starts a blank one that belongs to no survey. **Export report** (Page settings → Report file) saves the whole report — text, numbers, quotes, pictures and which questions its charts and maps show — as one file; **Import a report** on the Reports page brings such a file in, here or in another workspace. An imported report is not published and only the workspace sees it until you change that; a chart or map of a survey the workspace does not have is left out, and you are told which.

## Result

Visitors see the opening, the blocks in your order, and — for a frozen page — a "Data as of" date. Small groups show "Small groups are masked to protect privacy"; every map block shows a grid of how many respondents marked each square, never the individual points, lines, areas or dots; a square's popup lists the chosen sub-question answers in it, small groups masked. Only clean responses count: trashed, not-approved and on-hold responses are left out. The page carries the "Made with Mapsurvey" badge on Free.

**Unpublish** takes the page down; the address stops opening for visitors.

## Related

- [Sharing and access](/reference/sharing-and-access/)
- [Question types](/reference/question-types/) — which types can be published
- [Survey settings](/reference/survey-settings/) — the thanks page
