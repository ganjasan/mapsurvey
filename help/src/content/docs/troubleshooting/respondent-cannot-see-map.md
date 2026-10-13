---
title: The map is blank or grey
description: A respondent sees an empty grey box, a map with no background tiles, or nothing at all where the map question should be.
sidebar:
  order: 60
---

A respondent reports a grey rectangle, a map with markers but no streets or imagery behind them, or an empty space where the survey should be when it is embedded in another site.

## Why it happens

The map is drawn in the respondent's browser from several sources, and any of them can be blocked on their side.

- **Background tiles are blocked.** Streets and Topo basemaps come from Mapbox, Satellite from Esri. A corporate network, a strict ad blocker or a privacy extension leaves the markers over a grey background.
- **The map library is blocked.** The map code loads from unpkg.com and cdnjs.cloudflare.com; if those are blocked the map area stays empty.
- **The survey is embedded on a site that is not allowed to frame it.** When **Sites allowed to embed** on the share page lists specific sites, a page on any other host gets an empty frame. A host page served over plain `http://` cannot frame the survey either.
- **Third-party cookies are blocked in the embed.** The survey shows, but answers do not persist from page to page.
- **The browser is out of date.** Browsers several years old do not run the map code.
- **Self-hosted installation without a map token.** Streets and Topo need a Mapbox access token in the configuration.

## What to do

1. Ask the respondent to open the survey link directly, outside any embed, in a current browser. If the map appears there, the embed or their extensions are the cause.
2. Ask them to disable ad-blocking and privacy extensions for the survey page, or to try another network.
3. If the survey is embedded, open the share page and check **Sites allowed to embed**. Add the host of the embedding page and click **Save allowed sites**, or leave the list empty to let any site embed. The host page must use `https://`. See [Embed a survey](/how-to/embed-a-survey/).
4. If answers are lost between pages inside an embed, ask the respondent to open the link directly.
5. On a self-hosted instance, set the Mapbox token described in the project README and restart.

## If it keeps happening

[Contact support](https://mapsurvey.org/?support=1) with the survey link, the respondent's browser and device, whether the survey was opened directly or embedded (and where), and a screenshot. The first red line in the browser's developer console tells us which request was blocked.
