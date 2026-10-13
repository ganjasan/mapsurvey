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
3. Open a map block's **Block settings** and choose its **Point popup fields** — the sub-questions whose values a visitor sees when they click a point. Leave it empty for anonymous geometry. Free-text sub-questions cannot be shown.
4. Under **Page settings**, choose:
   - **Visibility**: **Public** is indexed by search engines and can be listed; **Unlisted** opens only by direct link and is not indexed.
   - **Data mode**: live data, or **Freeze snapshot** to publish a fixed copy. A frozen page keeps showing the snapshot until you press **Update snapshot** or **Back to live**.
   - **k-anonymity threshold**: groups smaller than this number are masked as "<K" on every chart and map. The default is 3; set it to 1 to switch masking off.
   - **Show response counter** and **Show “Take the survey” CTA** (the button shows only while the survey is open).
5. Press **Publish page**. The address is shown next to **Public URL**; **Copy public link** copies it, and the same link appears under **Results page** on the Share page.
6. To show the page to respondents after they finish, switch on **Show a “See the results” button** on the thanks page.

## Result

Visitors see the intro, the blocks in your order, and — for a frozen page — a "Data as of" date. Small groups show "Small groups are masked to protect privacy"; a spray area block shows a density grid of how many respondents painted each cell, never the dots. Only clean responses count: trashed, not-approved and on-hold responses are left out. The page carries the "Made with Mapsurvey" badge on Free.

**Unpublish** takes the page down; the address stops opening for visitors.

## Related

- [Sharing and access](/reference/sharing-and-access/)
- [Question types](/reference/question-types/) — which types can be published
- [Survey settings](/reference/survey-settings/) — the thanks page
