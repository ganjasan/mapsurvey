---
title: Share results publicly
description: Publish a page of charts and maps at a short address so respondents and the public can see what others said.
sidebar:
  order: 80
---

You end up with a public results page at `https://mapsurvey.org/r/<slug>/` showing aggregated answers — never individual ones — that you can link from the thanks page, a newsletter or a council website.

## Before you start

Reports are part of **Pro**. On a workspace without Pro a report opens read-only; the first change you make starts a 90-day Pro trial, with no card. When a trial or a subscription ends, published reports stay online at the same address with the numbers they had that day ("Data as of …"), you can still export them and make their PDF, and nothing is deleted.

- The survey is **Published**. A draft survey's results page cannot be published.
- Decide what the public should see. Text answers are never shown; choice, rating, number, range and thumbs questions become charts; map questions become maps; **Objects on the map** questions become per-object totals.

## Steps

1. Open the survey and choose the **Public results** tab. Mapsurvey has already drafted a page from your questions, one block per publishable question. The report itself is in the middle of the screen: you write and arrange it there. The outline of its blocks is on the left, and the panel on the right holds the settings of the block you clicked — or of the whole report when no block is selected.
   <!-- screenshot: the report builder — outline, the report, the settings panel -->
2. Arrange the blocks: drag a block by its handle, or use the arrows in the bar that appears over it; switch on **Hidden** in the panel for the ones you do not want; and press **Add block** — or the **+** between two blocks, to add one exactly there. In the library the blocks you write yourself come first; under **Questions** pick a question to add its chart or map.
3. Click a map block and, in the panel, choose its **Point popup fields** — the sub-questions a visitor sees summarised when they click a square of the map. Free-text sub-questions cannot be shown. The public map never shows a respondent's own point, line or area: it shows squares coloured by how many respondents marked them, and hides any square with fewer respondents than the k-anonymity threshold — a single pin at a front door can tell neighbours who answered and what they said. The exact points stay in **Responses** and in the export.
4. Click **Title and opening** in the outline for the **Report settings** in the panel, and choose:
   - **Visibility**: **Public** is indexed by search engines and can be listed; **Unlisted** opens only by direct link and is not indexed.
   - **Data mode**: live data, or **Freeze snapshot** to publish a fixed copy. A frozen page keeps showing the snapshot until you press **Update snapshot** or **Back to live**.
   - **k-anonymity threshold**: groups smaller than this number are masked as "<K" on every chart and map. The default is 3; set it to 1 to switch masking off.
   - **Show response counter** and **Show “Take the survey” CTA** (the button shows only while the survey is open).
5. Press **Publish**. Once the report is out, the same button reads **Published**: it shows the address with a button that copies it, and the same link appears under **Results page** on the Share page.
6. To show the page to respondents after they finish, switch on **Show a “See the results” button** on the thanks page.

## Start from a draft

You do not have to begin with an empty page. Press **New report** on the **Reports** page, or **Make a report** on a survey's Responses page, choose the survey and press one of the cards:

- **Consultation summary** — who took part, then every question people answered in the survey's order, with the survey's sections as headings.
- **Council paper** — numbered sections, results as tables, a place for recommendations.
- **Engagement update** — short, for while the survey is still open: the numbers, the maps and a link to take part.
- **You said — we did** — each result followed by a place to say what was done about it.

The draft is built by fixed rules from the answers, not written by an AI. It is not published. Answers to open questions arrive as a hidden **Quotes** block to pick from: delete the lines you do not want, then switch off **Hidden**. Places where you are expected to write arrive as hidden text blocks with a hint; write over the hint and un-hide them. **Blank report** starts empty, and **Copy an earlier report** gives you the same story to change for the next round.

## The next round

When a second survey asks the same questions — the usual way is to duplicate the first survey, which keeps every question's code — you do not rewrite the report. On **New report**, in **Copy an earlier report**, choose the report, choose the new survey under **for the survey**, and press **Copy**. The copy keeps your opening, your text and the order of the blocks; every chart, map, cross-tab and the engagement block now read the new survey. Numbers written as `{responses}` follow too; numbers you typed by hand are yours to change.

A block whose question the new survey does not have is not lost quietly. After the copy a message names each one, and in its place the copy holds a hidden note saying what the earlier report showed there. Add a block for the question that replaced it, or delete the note; hidden notes never reach the published page.

To show both rounds in one picture, add a **Compare** block: pick a question and the other survey. For each answer it shows the share of people in both surveys, with how many answered in each. The other survey needs a question with the same code. Small groups are hidden in each survey separately.

## Tell it as a story

The page is read top to bottom like an article, so write it like one. Under **Add block**, beside the results of a question, there are blocks you write yourself:

- **Heading** starts a section.
- **Text** is a paragraph, a list or a few of them, with bold, italics and links.
- **Image** is a picture with a caption — a photo, or a chart or map you made elsewhere.
- **Key numbers** is a strip of figures with a word under each. Type each figure and the word under it on the page; **Add a number** adds another. You type these numbers; they do not change when new answers arrive.
- **Quotes** shows what people wrote. Type or paste each quote on the page, with an optional source under it; **Add a quote** adds another. A quote is published exactly as you enter it, so leave out anything that names a person.

Blocks that follow the answers:

- **Cross-tab** puts two questions against each other — transport by age, say: how many people gave each pair of answers, among those who answered both. Pick the question for the rows and the one for the columns when you add it.
- **Engagement** shows how many people opened the survey, answered and finished, and how that went over time.
- A **map** block shows squares that count respondents. Switch on **Show the marks themselves** in the block's settings to show every place, line or area as it was drawn instead. A mark can point at someone's home, so decide whether that is right for your survey; the default stays the squares.
- **Numbers in the text** can follow the answers too. Write `{responses}` in a text, a key number or the opening paragraph and the page fills in how many people answered; `{opened}` and `{finished}` are the other two steps, `{marks:CODE}` the marks placed on a map question and `{respondents:CODE}` the people who answered a question, CODE being the question's code. A frozen page keeps the numbers of the day it was frozen. A count smaller than the privacy threshold reads "<3".

Set a block's **Width** to *Half width* to put two blocks side by side on a wide screen; on a phone they stack. The line above the title, the title and the opening paragraph are written at the top of the page itself. A key number or an opening that follows the answers shows the number on the page; click it to see and change its token.

All reports of the workspace are on the **Reports** page of the sidebar. **New report** starts a blank one that belongs to no survey. **Export report** (Report settings → Report file) saves the whole report — text, numbers, quotes, pictures and which questions its charts and maps show — as one file; **Import a report** on the Reports page brings such a file in, here or in another workspace. An imported report is not published and only the workspace sees it until you change that; a chart or map of a survey the workspace does not have is left out, and you are told which.

## Before you publish

**Publish** opens a short dialog first.

- **People in this report** lists what could point at a person: every quote you chose to show, written out; every map that shows the marks themselves; and a warning if small groups are not hidden. If there are quotes or such maps, tick **I have read the quotes and maps listed above** — the report is not published without it. Whether a quote or a mark may go out is your decision; the dialog makes sure you saw them.
- Below it are things that would look unfinished, each with a button: a block with nothing in it (**Delete the block**), a map nobody described (**Open the block** and say in a sentence what it shows — the sentence appears under the map and is read aloud by screen readers), a missing title. None of these stops you from publishing.
- Choose **who can open it** and whether the **numbers** stay live or are frozen as they are now.

The phone and screen buttons at the top show the report as on a phone or on a computer; **Preview** opens it in a new tab, exactly as readers get it.

## A PDF for the meeting pack

Under **Page settings → Report file** press **PDF (A4)**. The PDF is made in the background — a report with several maps takes up to a minute — and opens when it is ready. It holds the same text, numbers, charts and maps as the page, in the same order, with the report's address and the page number at the foot of every page; a block is never split between two pages.

A **frozen** report's PDF is made once: after that its published page shows a **PDF** link next to "Data as of", for everyone who can open the page. A **live** report's PDF shows the numbers of the moment you ask and is not linked from the page.

## Show it on another site, in slides or in a document

- **Embed the report.** Under **Page settings → Embed on another site** copy the code and paste it into your site's page. It always shows the published report and grows to its height. To put only one chart or map on a page, open that block and copy the code under **Use this block elsewhere**. The code works once the report is published as public or unlisted; list **Sites that may embed it** to keep it off other sites.
- **A chart or map as a picture, with its numbers.** In a block's settings, **PNG** downloads the block as a picture with its title and **CSV** its numbers. **Charts and maps (ZIP)** under Page settings → Report file gives all of them at once.

The numbers in a CSV are the ones the page shows: a group too small to show reads "<3" there too, and a map lists its squares, not people's marks, unless you chose to show the marks.

## See whether it is read

**Page settings → Readers** shows how many times the report's page was opened, how many times it was shown inside another site, and how many times its PDF was downloaded — in total and in the last 30 days. The numbers are counted on Mapsurvey's own server: the page loads no analytics script, and nothing about a reader is stored, so they are "times opened", not "people". Your own visits and your colleagues' are left out.

## Group it with tags

Under **Page settings → Tags** give the report the same tags as its surveys and datasets ("Riverside plan 2027"). The **Reports** page shows them and filters by one.

## From your assistant or your own code

With an assistant connected to Mapsurvey ([Use the MCP server](/how-to/use-the-mcp-server/)) you can ask for the report itself: "draft a consultation summary from the Riverside survey, add a paragraph about the bridge and show me the checks". The assistant drafts by the same rules as the cards, writes the blocks you ask for, and reads you the quotes and maps of marks before it may publish — it cannot publish those without your yes. The same operations are in the [REST API](/reference/api/) under `/reports`. Pictures are added in the editor.

## Result

Visitors see the opening, the blocks in your order, and — for a frozen page — a "Data as of" date. Small groups show "Small groups are masked to protect privacy"; every map block shows a grid of how many respondents marked each square, never the individual points, lines, areas or dots; a square's popup lists the chosen sub-question answers in it, small groups masked. Only clean responses count: trashed, not-approved and on-hold responses are left out. The page carries the "Made with Mapsurvey" badge on Free.

**Unpublish** takes the page down; the address stops opening for visitors.

## Related

- [Sharing and access](/reference/sharing-and-access/)
- [Question types](/reference/question-types/) — which types can be published
- [Survey settings](/reference/survey-settings/) — the thanks page
