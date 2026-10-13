---
title: FAQ
description: Short answers to the questions people actually ask us, each linking to the page that answers in full.
tableOfContents: false
---

<!--
Rules for this page (help/CONTRIBUTING.md):
- A question is added only when someone asked it: support chat, email, demo request,
  or a landing-page FAQ. Put the source in a comment right above the question.
- Answers are at most three sentences and link to the page that answers in full.
- Keep the groups below; add a jump link for every question in the list at the top.
-->

**Getting started**

- [Is Mapsurvey free to use?](#is-mapsurvey-free-to-use)
- [Do respondents need an account or an app?](#do-respondents-need-an-account-or-an-app)
- [Is Mapsurvey suitable for PPGIS and participatory research?](#is-mapsurvey-suitable-for-ppgis-and-participatory-research)
- [Can Mapsurvey run participatory budgeting?](#can-mapsurvey-run-participatory-budgeting)

**Surveys and questions**

- [What can respondents mark on the map?](#what-can-respondents-mark-on-the-map)
- [How do I ask follow-up questions about each place a respondent marks?](#how-do-i-ask-follow-up-questions-about-each-place-a-respondent-marks)
- [How do residents propose a project on the map?](#how-do-residents-propose-a-project-on-the-map)

**Maps and layers**

- [How do we show consultees the plans?](#how-do-we-show-consultees-the-plans)
- [Can residents react to each other's proposals?](#can-residents-react-to-each-others-proposals)

**Responses and export**

- [How do I get the raw spatial data into QGIS or ArcGIS?](#how-do-i-get-the-raw-spatial-data-into-qgis-or-arcgis)
- [Which export formats are there, and who owns the data?](#which-export-formats-are-there-and-who-owns-the-data)
- [How do responses get into the consultation report?](#how-do-responses-get-into-the-consultation-report)

**Sharing and embedding**

- [How do I share a survey with residents?](#how-do-i-share-a-survey-with-residents)
- [How do I show results back to the people who took part?](#how-do-i-show-results-back-to-the-people-who-took-part)

**Account and Pro**

- [What does Pro cost, and what does it add?](#what-does-pro-cost-and-what-does-it-add)
- [Are there per-project, per-survey or per-seat fees?](#are-there-per-project-per-survey-or-per-seat-fees)
- [Can one workspace run engagement for a whole city?](#can-one-workspace-run-engagement-for-a-whole-city)
- [What are the uptime and support arrangements?](#what-are-the-uptime-and-support-arrangements)

**Self-hosting**

- [Can we self-host Mapsurvey?](#can-we-self-host-mapsurvey)
- [Where is the hosted service's data stored, and can we keep data in the EU?](#where-is-the-hosted-services-data-stored-and-can-we-keep-data-in-the-eu)

## Getting started

<!-- source: landing /for-planners/, /for-researchers/, /for-government/, /for-educators/, /for-consultants/, /civic-engagement/, /alternatives/maptionnaire/, /alternatives/metroquest/ -->
### Is Mapsurvey free to use?

Yes. The Free plan is the full product, not a trial: every question type, unlimited surveys, responses and team members, every export format, and no time limit. Pro is an optional paid tier per workspace; see [Plans and billing](/reference/plans-and-billing/).

<!-- source: landing /for-planners/, /for-researchers/, /for-government/, /for-educators/, /for-consultants/, /community-engagement-platform/, /citizen-engagement-platform/, /public-consultation-software/, /civic-engagement/, /participatory-budgeting/ -->
### Do respondents need an account or an app?

No. Respondents open the survey link in any current browser, on a phone or a computer, and answer; there is nothing to install and no sign-up. Only the people who build surveys need an account. See [Sharing and access](/reference/sharing-and-access/).

<!-- source: landing /for-researchers/ -->
### Is Mapsurvey suitable for PPGIS and participatory research?

Yes. Point, line and polygon input is captured against your own questions and exports as GeoJSON with a CSV of the non-spatial answers, ready for QGIS, R or Python. [Designing a map survey](/learn/designing-a-map-survey/) covers the method; [Learn](/learn/) collects the background reading.

<!-- source: landing /participatory-budgeting/ -->
### Can Mapsurvey run participatory budgeting?

It runs the spatial side: residents pin where investment is needed, describe a project in place, and react to shortlisted locations on a shared map. It is not a ballot or budget-allocation tool, so run the final vote on a fixed budget elsewhere. [Designing a map survey](/learn/designing-a-map-survey/) shows how to structure the proposal stage.

## Surveys and questions

<!-- source: landing /for-planners/, /for-government/, /for-educators/, /community-engagement-platform/, /public-consultation-software/, /alternatives/maptionnaire/, /alternatives/social-pinpoint/, /alternatives/metroquest/ -->
### What can respondents mark on the map?

Points, lines (routes) and polygons (areas), each as its own question type, alongside ordinary survey questions. A respondent can place several marks on one question, and you can attach questions to each mark. See [Question types](/reference/question-types/) and [Add a map question](/how-to/add-a-map-question/).

<!-- source: landing /civic-engagement/ ("How do you engage people on a map?") -->
### How do I ask follow-up questions about each place a respondent marks?

Add sub-questions to the map question: one or two short questions that appear for every point, line or area the respondent places. Keep them few; the answer rate drops with every extra field. [Add sub-questions](/how-to/add-sub-questions/) shows the steps.

<!-- source: landing /participatory-budgeting/ -->
### How do residents propose a project on the map?

Build a map question that asks for a point or an area, then attach sub-questions for what to build, why, and a photo. Residents open the link, mark the place and answer; no account is needed and it works on a phone. See [Add a map question](/how-to/add-a-map-question/) and [Add sub-questions](/how-to/add-sub-questions/).

## Maps and layers

<!-- source: landing /public-consultation-software/ -->
### How do we show consultees the plans?

Upload the proposal as a reference layer (GeoJSON, exported from any GIS). Respondents see the scheme beneath the map, and an **Objects on the map** question lets them answer about each feature in it, such as a proposed crossing or a new route. See [Add a reference layer](/how-to/add-a-reference-layer/).

<!-- source: landing /participatory-budgeting/ -->
### Can residents react to each other's proposals?

Yes. Show the shortlisted proposals as a layer and add an **Objects on the map** question; residents give each one a thumbs up or down and a comment. Reactions are one per browser session without voter authentication, so use them to prioritise rather than as a binding vote. See [Question types](/reference/question-types/).

## Responses and export

<!-- source: landing /for-planners/, /for-researchers/, /for-government/, /for-educators/, /for-consultants/, /civic-engagement/, /participatory-budgeting/, /alternatives/maptionnaire/, /alternatives/social-pinpoint/, /alternatives/metroquest/ -->
### How do I get the raw spatial data into QGIS or ArcGIS?

Export the responses from the survey's responses page. The ZIP export holds GeoJSON for every answer with geometry plus a CSV of the other answers, and GeoPackage, Shapefile and KML are available directly. [Export responses](/how-to/export-responses/) walks through it.

<!-- source: landing /citizen-engagement-platform/, /community-engagement-platform/ ("Do we own the data we collect?") -->
### Which export formats are there, and who owns the data?

ZIP (GeoJSON plus CSV), XLSX, CSV, GeoPackage, Shapefile and KML, at any time and on every plan. The data is yours: you can export it and delete the survey with its responses whenever you choose. [Exports](/reference/exports/) lists what each format contains.

<!-- source: landing /public-consultation-software/ -->
### How do responses get into the consultation report?

Export every response, with its geometry, in the format your GIS or spreadsheet reads, or publish an aggregated public results page for the record. Individual free-text answers are never published. See [Export responses](/how-to/export-responses/) and [Share results publicly](/how-to/share-results-publicly/).

## Sharing and embedding

<!-- source: landing /civic-engagement/ ("How do you engage people on a map?"), /for-educators/ ("Do students need to install anything?") -->
### How do I share a survey with residents?

Publish the survey and share its link: in a newsletter, as a QR code on a notice, or embedded on the project page you already have. Respondents need no account and can answer on a phone. See [Sharing and access](/reference/sharing-and-access/) and [Embed a survey](/how-to/embed-a-survey/).

<!-- source: landing /civic-engagement/ ("How do you engage people on a map?") -->
### How do I show results back to the people who took part?

Publish a public results page with aggregated maps and charts, so participants see that their input was counted. Free-text answers stay private. [Share results publicly](/how-to/share-results-publicly/) shows how to set one up.

## Account and Pro

<!-- source: landing /community-engagement-platform/, /citizen-engagement-platform/, /public-consultation-software/, /civic-engagement/, /participatory-budgeting/ -->
### What does Pro cost, and what does it add?

Pro is $49 a month or $490 a year per workspace, with any number of users, surveys and responses. It removes the "Made with Mapsurvey" badge from your surveys and adds direct support from the developer, including consulting, analysis and reports. See [Plans and billing](/reference/plans-and-billing/) and [Upgrade to Pro](/how-to/upgrade-to-pro/).
<!-- TODO verify: the pricing section on mapsurvey.org lists "Public results pages" under Pro, but billing/features.py gates only 'unbranded' and 'pro_help'; the public results editor is not feature-gated in code. Confirm which is intended before adding it here. -->

<!-- source: landing /for-consultants/, /citizen-engagement-platform/ -->
### Are there per-project, per-survey or per-seat fees?

No. Free has no cap on surveys, responses or team members, and Pro is one flat price per workspace with no per-project, per-seat or per-response metering. See [Plans and billing](/reference/plans-and-billing/).

<!-- source: landing /civic-engagement/ -->
### Can one workspace run engagement for a whole city?

Yes. A workspace holds any number of surveys, team members and respondents; each survey has its own link and results page, and every answer exports to the city's GIS. See [Plans and billing](/reference/plans-and-billing/).

<!-- source: landing /citizen-engagement-platform/ -->
### What are the uptime and support arrangements?

The hosted service has no contractual SLA; deploys are zero-downtime, the stack is monitored, and incidents are fixed by the developer who runs it. Pro includes direct support from the developer, Free is supported by email and the public issue tracker, and an organisation that needs an uptime guarantee can self-host. See [Plans and billing](/reference/plans-and-billing/).

## Self-hosting

<!-- source: landing /for-planners/, /for-researchers/, /for-government/, /for-educators/, /for-consultants/, /community-engagement-platform/, /public-consultation-software/, /participatory-budgeting/, /alternatives/maptionnaire/, /alternatives/social-pinpoint/, /alternatives/metroquest/ -->
### Can we self-host Mapsurvey?

Yes. Mapsurvey is open source under the AGPLv3 and ships as a Docker Compose stack with a PostGIS database, so response data stays on servers you control at no licence cost. The [README on GitHub](https://github.com/ganjasan/mapsurvey) has the installation steps.

<!-- source: landing /community-engagement-platform/, /citizen-engagement-platform/, /alternatives/maptionnaire/ ("Can I self-host or keep data in the EU?") -->
### Where is the hosted service's data stored, and can we keep data in the EU?

The hosted service at mapsurvey.org runs in the United States (Render, Oregon region). If your rules require the data to stay in your own jurisdiction, self-host the same Docker stack on your own infrastructure; a choice of hosting region for the hosted service is on the Pro roadmap. The [trust page](https://mapsurvey.org/trust/) lists the processors.

---

Did not find your question? [Contact support](https://mapsurvey.org/?support=1) — if it is a common one, it ends up here.
