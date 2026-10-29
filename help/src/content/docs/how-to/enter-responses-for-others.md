---
title: Enter responses for others
description: Type in answers collected on paper, in an interview or in the field, keep them apart from online answers, and add questions only the person entering sees.
sidebar:
  order: 75
---

You end up with paper sheets, interview notes or field observations in your survey's responses, marked with where they came from and who typed them in.

## Before you start

- Your organisation is on **Pro**. Without Pro the **Enter a response** button shows a lock.
- You have the **editor** role or higher on the survey.
- You know which version of the survey the paper form was printed from, if you changed the survey since.

## Steps

1. Open the survey's **Responses** page and press **Enter a response**.
2. Choose where the answers come from:
   - **Paper form** for a filled sheet.
   - **Assisted interview** when you fill the survey in with someone, in person or by phone.
   - **Field observation** for what you or a field worker recorded on site.
   - **Other** for anything else.
3. If the survey has more than one version, pick the one the sheet was printed from. If it has more than one language, pick the language of the answers.
4. Press **Start entering**. The survey opens page by page, like a respondent sees it, with a yellow bar on top that says you are entering a response.
5. Type in the answers and press **Next** on each page. Questions marked required for respondents do not stop you: a blank on paper stays blank.
6. On the last page press **Finish**. Press **Enter the next one** to start the next sheet with the same source, version and language.

## Questions only the person entering sees

Some things belong on the entry form but not in the public survey: the sheet number, the event where the sheet was collected, a note that a handwritten answer was hard to read.

1. On the survey's **Build** page, open the question, group or page.
2. Under **Who sees this**, choose **Operators only**.

Respondents never see it, and on the entry form it behaves like any other question, including **Required**. **Respondents only** works the other way round: the question stays off the entry form. On a published survey, changing who sees a question goes through **Unpublished changes**.

## Where entered responses show up

- **Responses** has a **Source** column. Filter it to see only paper sheets, or only online answers. The response drawer names the person who entered it.
- Entered responses count as responses on the Overview, in the charts and on a public results page.
- They are not visits: the **Perf** pane and its funnel count only people who opened the survey link.
- Every export has `source` and `entered_by` columns in its sessions table.

## Related

- [Print a paper form](/how-to/print-a-paper-form/)
- [Export responses](/how-to/export-responses/)
- [Edit a published survey](/how-to/edit-a-published-survey/)
- [Upgrade to Pro](/how-to/upgrade-to-pro/)
