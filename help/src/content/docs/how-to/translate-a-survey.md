---
title: Translate a survey
description: "Offer the survey in several languages: add languages, translate every text, and let respondents pick theirs on the first screen."
sidebar:
  order: 14
---

You end up with one survey that respondents take in the language they choose, with every title, question, hint and answer option translated, and one set of results.

## Before you start

- Decide on the primary language. It is the language you write the original texts in, and the fallback respondents see wherever a translation is missing.
- Have the translations ready, or plan time for them. There is no machine translation inside the editor.

## Steps

### Add the languages

1. Open **Survey settings**.
2. Under **Languages**, select every language respondents should be able to choose. The first one listed is the primary language. (When creating a survey, the same field is called **Available languages**.)
3. Save. The editor now shows a field per language wherever text is shown to respondents.

### Translate sections

1. Select a section in the left column.
2. The base **Title** and **Subheading** fields are now labelled with the primary language. Below them, the **Translations** block has a title and subheading field for each other language. Fill them in; the section autosaves.
3. If the section has a custom **Button label** (for example "Start" on a welcome section), the **Translations** block carries a field for it in each language too. Leave it empty to keep the default Next/Finish wording, which is translated for you.


### Translate questions and their options

1. Open each question with its pencil icon and scroll to **Translations**.
2. Fill in **Name (language)** and **Subtext (language)** for every language.
3. For **Choices**, **Multiple Choices**, **Rating** and **Range** questions, the **Choices** table has one **Name** column per language; the **Code** stays the same across languages, which is what keeps the results in one column.
4. Do the same for every sub-question of a map question; their popups are translated the same way.
5. Click **Save**.

<!-- screenshot: the Translations block of a question dialog with Name and Subtext fields for two languages -->

### Check and publish

1. In the **Live preview**, use the **Language** switcher to view the section in each language. Anything still in the primary language is an untranslated field.
2. Click **Publish — open for responses** (or **Publish changes** on a live survey). If any text has no translation, Mapsurvey lists the gaps and warns that those respondents will see the primary language instead. You can go back and fill them, or publish anyway and translate later: fixing wording and translations on a published survey saves straight to the live survey, with no new version.

## Result

Respondents who open the link see a language screen first, with each language in its own name (`English`, `Deutsch`, `Русский`). Their choice applies to the whole survey and is stored with their response, so the export's `session_language` column tells you which language each respondent used. Answers from all languages land in the same questions and the same columns.

Map labels, buttons and messages that belong to Mapsurvey itself (such as **Apply** or "Next") follow the respondent's language automatically for the interface languages Mapsurvey ships with; your survey content can be in any language.

## Related

- [Survey settings](/reference/survey-settings/)
- [Edit a published survey](/how-to/edit-a-published-survey/)
- [Exports](/reference/exports/)
