---
title: Edit a published survey
description: Fix wording in place on a live survey, or make structural changes in unpublished changes and publish them as a new version.
sidebar:
  order: 15
---

You end up knowing which edits reach respondents immediately and which go through unpublished changes, and how to publish or discard those changes.

## Before you start

- The survey is **Published** and has collected at least one response. Before the first response, **Back to Draft** is still offered in the publishing widget and lets you edit freely.
- You need the editor role or higher on the survey; publishing changes is for the survey owner.

## Which edits save in place

While people are answering, these edits save straight to the live survey, and the next respondent sees them:

- wording: survey name, section titles and subheadings, question names and subtext;
- translations;
- answer options of a choice question (keep the codes stable, because codes are what the results are keyed on);
- survey settings such as the thank-you page, base maps, map position and reference-layer styling.

Everything that changes *what is asked* goes through unpublished changes: adding, deleting or reordering questions and sections, moving a question to another section (**Move to section…** in the question row), changing a question's type, adding sub-questions, and changing visibility rules. In the editor these controls are disabled on a live survey and show the hint **Create a draft to edit**.

## Steps

### Start unpublished changes

1. Click a disabled control, or **Change structure (unpublished changes)** in the publishing widget.
2. Read the **Change the structure of a live survey** dialog and click **Start unpublished changes**. If you prefer not to be asked next time, tick **Don’t ask again**.
3. The editor now carries the badge **Unpublished changes** and a banner: respondents keep the live survey until you click **Publish changes**. Make your edits; everything is allowed here, and the **Live preview** shows the draft.

While unpublished changes exist, the live survey itself is read-only, including its wording: every edit, however small, goes into the draft and reaches respondents when you publish. Finish or discard the draft before you need an in-place fix again.

You can leave and come back. The survey's card on the dashboard and its publishing widget offer **Go to draft** and **Continue editing the draft →**, and the live survey keeps collecting meanwhile. On the draft, the **Responses** page still shows the live survey's responses; test responses you make while previewing the draft are kept apart and never counted with the real ones.

<!-- screenshot: the editor with the Unpublished changes badge and the banner above the section list -->

### Publish the changes

1. Click **Publish changes**.
2. Mapsurvey checks the draft against the live version. If it finds breaking changes — for example a question whose type changed, so existing answers no longer fit — it lists them under **Compatibility Issues Found**. **Cancel** to reconsider, or **Force Publish** if you accept that the old answers to those questions will sit under a different column.
3. If the survey has several languages and some new text is untranslated, you are warned that those respondents will see the primary language. Publish anyway or go back and translate.
4. Confirm with **Publish**.

New respondents get the updated survey right away. Anyone in the middle of the survey finishes the version they started.

### Or discard them

Click **Discard changes** and confirm with **Discard**. The draft, including any test responses made on it, is deleted; the live survey stays exactly as it is.

## Result

Publishing creates a new version: the previous one is archived with its responses, and the publishing widget shows the version number. On the **Responses** page and in the export dialog, a **Version** selector lets you look at **All versions**, the **Current** one, or any earlier version on its own. Questions that kept their code are reported as one column across versions. The survey link does not change.

## Related

- [Publish and share](/start-here/publish-and-share/)
- [Export responses](/how-to/export-responses/)
- [Sharing and access](/reference/sharing-and-access/)
