---
title: Writing questions people can answer on a map
description: How to word a map task, turn follow-ups into attributes, build choice lists, and keep a survey short enough to finish on a phone.
sidebar:
  order: 3
---

A map question is answered by doing something, not by reading and ticking. The wording has to tell the respondent what to do, where, and what will be asked once they have done it. This essay covers the wording of the map task, the sub-questions attached to each feature, the choice lists behind them, the screen all of this appears on, and the two constraints that override everything else: length and the phone.

## The respondent's screen

Design rules only make sense against the real interface. A Mapsurvey respondent opens a page with the questions on one side and a map on the other. The things to know, from Part 1 of [survey-design-rules.md](https://github.com/ganjasan/mapsurvey/blob/master/docs/research/survey-design-rules.md):

- **A section is one screen.** The respondent moves between sections with **Next**. A long section means long scrolling, not more pages, so a section with twelve questions is twelve questions on one screen.
- **Map questions are answered on the map.** The respondent places a marker (point), draws a path (line) or draws an area (polygon). One map question accepts several features.
- **Sub-questions open in a popup on the feature** the respondent placed a moment ago. They are the only way to attach attributes to a place.
- **Sub-question names become column names on export.** A sub-question called "What is wrong here?" becomes that column in the analyst's GIS. This is the single highest-leverage naming decision in the survey.
- **Scale questions derive their scale from their choice codes**, which must be integers in ascending order.
- **A multilingual survey needs every question in every language**, or the respondent silently gets the primary one.

Full details of each type are in [Question types](/reference/question-types/).

## Wording the map task

The task is a verb, a geometry and one thing: "Mark where you usually wait." "Draw the shortcut you actually walk." "Outline the area that needs the biggest change." A respondent who reads the question should know whether they are placing a dot, tracing a path or drawing a shape, and how many of them are wanted ("up to three places").

Two findings from general survey methodology carry over to the map. Tourangeau, Rips and Rasinski (2000) describe answering as four steps: understanding the question, retrieving what is relevant, judging, and fitting the answer to the format ([*The psychology of survey response*](https://doi.org/10.1017/CBO9780511819322)); a map question that is vague at step one ("Where are the problems?") produces pins nobody can interpret. Krosnick (1991) describes *satisficing*, the shift to a good-enough answer when the task is hard or long ([*Response strategies for coping with the cognitive demands of attitude measures*](https://doi.org/10.1002/acp.2350050305)); on a map, satisficing is a pin dropped in the centre of the screen. So ask about something the respondent has experienced: "the route you walk", not "the best route".

Avoid two wordings. "Where would you like to see improvements?" has no answer that is not everywhere. And a question with two subjects ("mark places that are valued or unsafe") produces one layer of pins with no way to tell them apart; make it two questions or a sub-question.

## Sub-questions are attributes

Everything a respondent says about a place is a sub-question on that place, and every sub-question is a column. Name them as the analyst will read them: "Reason", "What is missing", "How often", not "Q3b" and not a full sentence. Keep each one to a single attribute. A pin with three sub-questions, a choice list, a rating and an optional comment, is about the limit before the popup becomes a form.

The Remington survey asked for a short explanation with every pin, and 717 explanations turned a dot map into something planners could quote ([Neighbourhood plan](/use-cases/neighbourhood-plan/)). The Pszów survey put "what is missing here?" as a checkbox list on the waiting-spot pin, and 33 of 53 answers said shelter ([Public space microplanning](/use-cases/public-space-microplanning/)). Both are one popup, one attribute at a time.

If a follow-up only applies to some answers (a comment field after "Other", a severity rating after "fouling here"), make it conditional rather than showing it to everyone; see [Make a question conditional](/how-to/make-a-question-conditional/).

## Choice lists

A choice list should be exhaustive, mutually exclusive where it is single-choice, short, and written in the respondent's words. Four to seven options is the usual range on a phone; a list that needs scrolling inside a popup loses the options at the bottom. Put the options in a sensible order (frequency, severity, or the order a planner will act on them), not alphabetically, unless the list is long enough that people search it.

Prefer closed answers because they are answered more often and aggregate without hand-coding, and leave one open door: an "Other" with a comment, or one open question at the end. The Whitehouse bins survey had four reasons and an optional comment; the four reasons gave the council its table, and the comments told it why a particular corner mattered ([Where to put the bins](/use-cases/where-to-put-the-bins/)).

Two mechanical rules. If a question is a scale (rating, range), its choice codes are the scale: integers, ascending, so "1 = very unsafe" to "5 = very safe". And "neutral" belongs in the middle, "don't know" at the end, outside the scale; a "don't know" coded 3 is a bug in the data.

## Length

Galesic and Bosnjak (2009) randomised the announced length of a web survey and found that longer surveys had lower start and completion rates, and that answers to questions placed late in a long survey were shorter and more uniform ([*Effects of questionnaire length on participation and indicators of response quality in a web survey*](https://doi.org/10.1093/poq/nfp031)). A map task is heavier than a tick, so the budget is smaller than for a plain survey. The surveys in the use cases took a median of 90 seconds (one pin, one reason), seven minutes (six map tasks and a demographics page), and about 18 minutes (nine pages, three map questions, several open questions); the first two were completed by most who started, the third by 146 of 350 who opened the link.

Order by priority, not by logic: the map task the survey exists for goes first, demographics last. If the survey is long because the client wants many things, cut, or split it into two surveys.

## Mobile

Most respondents are on a phone: 38 of 39 in Whitehouse, seven in ten in Remington, "predominantly" in Pszów. Antoun, Couper and Conrad (2017) compared the same web survey on phones and PCs and found that answer quality was broadly similar, but open-text answers were shorter on phones and completion took longer ([*Effects of mobile versus PC web on survey response quality*](https://doi.org/10.1093/poq/nfw088)). On a map survey, the phone adds a small screen shared between the map and the questions, a finger instead of a cursor, and often a walk in progress. What follows for wording:

- One map task per screen, and the task sentence short enough to read without scrolling the map away.
- Say what to tap. "Tap **Place a marker**, then tap the map" is not condescending on a 6-inch screen; it is the instruction the Whitehouse council had to add after the fact.
- Prefer choices to typing. An optional comment is fine; a required paragraph is not.
- Expect pins to be less precise than on a desktop, and do not ask for precision the respondent cannot give ("mark the exact lamp post").
- Preview the survey on a phone before publishing, not only in the editor.

## When you build it

The map task itself is [Add a map question](/how-to/add-a-map-question/); the attributes on each feature are [Add sub-questions](/how-to/add-sub-questions/); the full list of types and their export behaviour is in [Question types](/reference/question-types/) and [Exports](/reference/exports/). To see how the column names come out before respondents arrive, publish to a test audience, answer once, and run [Export responses](/how-to/export-responses/).
