---
title: Embed a survey
description: Put a published survey inside a page on your own website with the snippet from the Share page.
sidebar:
  order: 60
---

You end up with the survey running inside a box on your own site — a council page, a project site, Tilda, Webflow, Wix, Squarespace or WordPress — with responses landing in Mapsurvey as usual.

## Before you start

- The survey is **Published**. The Share page shows no embed code for a draft or testing survey.
- You can edit the page on your site where the survey goes, or paste HTML into it.

## Steps

1. Open the survey and choose **Share** in its navigation.
2. Scroll to **Embed on your site** and press **Copy embed code**. The snippet is an `<iframe>` pointing at your survey plus one `<script>` tag that loads `/embed.js`.
   <!-- screenshot: the Embed on your site section with the snippet and copy button -->
3. Paste the snippet into your page where the survey should appear. In Notion, Ghost or a self-hosted WordPress you can instead paste the survey link; those platforms pick up the survey from it.
4. If a section uses the map layout, set the iframe `height` in the snippet to what you want — a map fills whatever height the box has. Form sections grow with their content on their own.
5. If the survey should be embeddable only on your sites, type them under **Sites allowed to embed**, one per line — `city.example.org`, or `*.example.org` for every subdomain — and press **Save allowed sites**. Leave the list empty to let any site embed the survey. Notion and other platforms that embed from a pasted link check this list from their own servers, so for them it has to stay empty.
6. Open your page and answer a section to check that the box shows the survey and that it appears under **Responses**.

## Result

The survey runs inside the frame. Form pages resize the frame to their content (that is what `embed.js` does); map pages keep the height you set. When a respondent finishes, they see the thanks page inside the frame — if the survey is set to open a web address after the last page, the frame shows a **Continue** button to it instead of navigating your page away. The "Made with Mapsurvey" badge shows inside the embed too; removing it is part of Pro.

Safari and every iOS browser block cookies inside a third-party frame. Mapsurvey handles that itself — a framed survey carries its own session — so there is nothing for you to set up and nothing for respondents to allow.

## Related

- [Sharing and access](/reference/sharing-and-access/)
- [Survey settings](/reference/survey-settings/) — "After the last page"
- [Plans and billing](/reference/plans-and-billing/) — removing the badge
