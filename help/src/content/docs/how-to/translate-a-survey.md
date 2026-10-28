---
title: Translate a survey
description: "Offer the survey in several languages: add languages, translate every text in one table or through a CSV, and let respondents pick theirs on the first screen."
sidebar:
  order: 14
---

You end up with one survey that respondents take in the language they choose, with every title, question, hint and answer option translated, and one set of results.

## Before you start

- Decide on the primary language. It is the language you write the original texts in, and the fallback respondents see wherever a translation is missing.
- Have the translations ready, or know who will write them. A bilingual colleague can work in the **Translations** tab; an outside translator can work in a spreadsheet through the CSV export and import. There is no machine translation inside the editor yet.

## Steps

### Add the languages

1. Open the **Translations** tab of the survey (between **Survey** and **Responses**).
2. With one language only, the tab offers a language search; pick the second language. On a survey that already has several, choose **Add language…** at the end of the target-language list. Adding a language is the workspace owner's action; removing one stays in **Survey settings → Languages**, where the first language listed is the primary.

### Translate in the table

The tab shows every text of the survey once, in the order respondents see it: page titles and intros, the Next button, questions, help texts, Formatted text blocks, answer options, group titles and the thank-you page. The original is on the left, read-only; the translation is on the right and saves as you leave the field.

1. Pick the pair of languages at the top: the source column (the primary language, or another language of the survey when the translator reads that one better) and the target.
2. Type the translations. A text used in several places — "Other", "(Select all that apply)" — is one row with a count (×6); one translation fills every place. Click the count to see where it is used.
3. When the same words need different wording in context ("Walk" as an activity and as a way of getting there), click **Translate separately** under that row and fill each place on its own. **Use one translation** merges them again.
4. Use the chips above the table to show only **Missing** or **Outdated** rows. A row is outdated when the original was edited after it was translated: check the translation and save it to clear the mark.
5. Every row links back to its place in the editor — the page, the question dialog, the thank-you panel — for the full context.

<!-- screenshot: the Translations tab with a group row ×6 unfolded and an outdated row -->

Rich texts (page intros, help texts, Formatted text, the thank-you page) are edited with the same formatting toolbar as the original.

The translation fields in the question, section and group dialogs show the stored text and open its row on the tab; translations are written on the tab only.

### Work with an outside translator

1. Choose the target language and click **Export CSV**. The file has one row per text: a `key`, the page, the element, the `source` text, the `translation` (empty where missing) and the status. Rich texts are exported as plain paragraphs.
2. The translator fills the `translation` column in a spreadsheet and sends the file back. A spreadsheet built by hand in the same shape works too: rows without a key are matched by their source text.
3. Click **Import CSV**, choose the file, and tick **Overwrite translations that already exist** only if the file should replace what is already translated; otherwise existing translations are kept and reported as skipped.
4. Read the report above the table: how many rows were filled, overwritten or skipped, and which source texts were not found in the survey. Nothing is dropped silently.

Bold and other formatting inside a paragraph does not travel through CSV; fix those rows in the table afterwards. Outdated is tracked from the moment a translation is saved in the table, through the import or an API client — translations written before that read as translated until they are saved again.

### Check and publish

1. In the **Live preview**, use the **Language** switcher to view the section in each language. Anything still in the primary language is an untranslated field.
2. Click **Publish — open for responses** (or **Publish changes** on a live survey). If any text has no translation or is outdated, Mapsurvey lists the gaps and warns that those respondents will see the primary language instead. You can go back and fill them, or publish anyway and translate later: a translation saved on a published survey goes straight to the live survey, with no new version.

## Result

Respondents who open the link see a language screen first, with each language in its own name (`English`, `Deutsch`, `Русский`). Their choice applies to the whole survey and is stored with their response, so the export's `session_language` column tells you which language each respondent used. Answers from all languages land in the same questions and the same columns.

Map labels, buttons and messages that belong to Mapsurvey itself (such as **Apply** or "Next") follow the respondent's language automatically for the interface languages Mapsurvey ships with; your survey content can be in any language.

## Related

- [Survey settings](/reference/survey-settings/)
- [Edit a published survey](/how-to/edit-a-published-survey/)
- [Exports](/reference/exports/)
