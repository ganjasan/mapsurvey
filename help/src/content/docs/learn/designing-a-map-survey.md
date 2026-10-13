---
title: Designing a map survey
description: Ten design rules for map-based surveys, the evidence behind each, and the four things research says go wrong anyway.
sidebar:
  order: 2
---

A map survey fails in a way a plain survey does not: it can look finished and collect nothing. The rules below come from PPGIS research and from the surveys that have run on Mapsurvey. They are maintained with their sources in the Mapsurvey repository, in [survey-design-rules.md](https://github.com/ganjasan/mapsurvey/blob/master/docs/research/survey-design-rules.md); this essay explains them.

## Lead with points; use polygons sparingly

Point mapping is simpler for lay participants and costs less effort per answer than drawing areas. Brown and Kyttä (2014) make this point in their review of PPGIS methods ([*Key issues and research priorities for PPGIS*](https://doi.org/10.1016/j.apgeog.2013.11.004)), citing Brown and Pullar (2012), who compared the two and found points produced comparable spatial information at lower respondent burden ([*An evaluation of the use of points versus polygons in PPGIS*](https://doi.org/10.1080/13658816.2011.585139)). Mapsurvey's own numbers agree: across production surveys, point questions are answered by 32% of the respondents who reach them, lines by 31%, polygons by 16.5%, against 40–48% for non-map questions. A draft that scatters polygons looks thorough and collects little.

Match the geometry to the intent (Alderton et al. 2026, [*Opportunities and next steps for advancing PPGIS methodology*](https://doi.org/10.1080/23748834.2026.2644000)): **points** for places visited or things observed, **lines** for routes actually travelled, **polygons** for perceived extents, such as "the area you think of as your neighbourhood". The Pszów microplanning survey used all three, each where it fitted: pins for where people wait, lines for the shortcuts they walk, an outline for the area needing the biggest change ([Public space microplanning](/use-cases/public-space-microplanning/)).

## One mapping task per survey

Every map question is a separate act of map work: find the place, choose the tool, place the feature, answer the popup. Ask for one, attach sub-questions to it, and let respondents add several features if they have more to say; "mark up to three places" is one task, not three. Where a survey needs more than one task, put the most important first, because completion drops with each.

## Decide whose places the map collects

Observation surveys ask respondents about the world around them; self-registration surveys ask them to put *themselves* on the map, their business, plot or project. The two share mechanics and need opposite wording. If the audience is the thing being mapped, write in the second person, collect one main feature per respondent, and let the sub-questions describe that place. The full argument is in [What participatory mapping is](/learn/what-participatory-mapping-is/).

## Ask what people already do, not only what is wrong

A Vienna study of summer heat (Seebauer et al. 2024, [*Feeling hot is being hot?*](https://doi.org/10.1016/j.scitotenv.2024.173952), n = 1,983) enters adaptive behaviour, what people already do to cope, as the first block of every analysis, and finds that the felt burden stays elevated even after adaptation. Without that block, "not affected" and "coping alone" look the same in the data, and they need opposite responses. Generalised: ask what the respondent currently does about the problem, not only whether it bothers them. "Where do you usually wait?" collected the single most agreed-on location in the Pszów survey.

## Collect what works, not only what is broken

Lehnert et al. (2023) had residents of Plzeň and Olomouc map both thermal "hotspots" and "coolspots"; the planning-relevant result was the uneven distribution of the good places, not the bad ones ([*Thermal comfort in urban areas on hot summer days and its improvement through participatory mapping*](https://doi.org/10.1016/j.landurbplan.2023.104713)). A survey that only harvests complaints cannot tell anyone what to protect. Remington asked for valued places first, and 86 residents put 274 pins on the parks, gardens and trails they wanted kept ([Neighbourhood plan](/use-cases/neighbourhood-plan/)).

## Make access an explicit attribute

A place that costs money, closes early, cannot be reached without a car or is not barrier-free is not available to the people a public plan exists to serve. A 2025 green-space equity survey in Bochum built on this distinction ([Urban Forestry & Urban Greening](https://doi.org/10.1016/j.ufug.2025.128989)). Where the survey is about a resource, ask about reaching it, not only about liking it: "How do you get here?" as a sub-question on the pin.

## Turn planner assumptions into questions

In the Lehnert et al. study, citizens suggested water features far less often than the planners expected. When a brief carries an assumption about what people want, phrase it as an option to be chosen or rejected, not as the structure of the survey. "Where would you plant one large shade tree?" assumes a tree is wanted; "What is missing here?" with "shade", "seating" and "shelter" as options lets the data say so. Pszów asked both, and shelter and seating were named more often than anything else.

## Assume weak map literacy and partial local knowledge

PPGIS presumes spatial awareness, digital literacy, map reading and familiarity with the place, and so excludes young children, some older adults and newcomers (Alderton et al. 2026; Laborgne and Klöcker 2023 report exactly this from a heat-relief survey in Karlsruhe, [*Exploring PPGIS as a way of digital participation*](https://doi.org/10.1007/978-3-031-32664-6_15)). Two consequences for a draft: keep the map task singular and unambiguous, and make sure the survey still yields usable answers from someone who never touches the map. In the Whitehouse bins survey, residents at first tapped the map instead of the placement button, and the council renamed the prompt mid-survey ([Where to put the bins](/use-cases/where-to-put-the-bins/)). A reference layer of what already exists orients people.

## Keep required fields minimal

Self-selected online participation already skews toward the engaged, and internet PPGIS with random household sampling averages 13–15% response (Brown and Kyttä 2014). Required questions that feel like an interrogation cost responses from exactly the harder-to-reach people. Require the mapping task if anything; nothing else. Put demographics last and accept that some will not finish them.

## Prefer closed answers, but leave one open door

Choice, multiple-choice and rating questions are answered more often than free text and aggregate without manual coding; Whitehouse's four reasons for a bin produced a table the council could read in an evening. Keep one or two open questions for what the option list missed; that is where the surprises are. Remington's open question about a typical day ten years ahead drew 115 answers, and the closed bridge that dominated the mapping turned up unprompted in 32 of them.

## Ask only what the creator can act on

Demographics are worth their length only when the results will be segmented by them. Every question a respondent cannot see the point of is a chance to abandon the survey. Before adding a question, name the decision it changes; if there is none, cut it.

## What the research says will go wrong anyway

Worth telling a client before they discover it.

- **Sampling, not software, is the data-quality problem.** Brown and Kyttä treat sampling design as the central determinant of whether PPGIS data can legitimately inform a decision. Brown, Kelly and Whitall (2014) compared a random household sample with volunteer participants in a public-lands survey and found the two "publics" mapped differently ([*Which 'public'? Sampling effects in PPGIS and VGI*](https://doi.org/10.1080/09640568.2012.741045)). Count the answers, not the link opens: Remington's 350 opens became 146 completed surveys.
- **The digital divide excludes the target group.** A plan for the elderly, ill and isolated is aimed at the people least likely to answer an online map. Make PPGIS one channel among several; paper copies handed out in person are part of the design, not a fallback.
- **Self-reported geometry needs cleaning.** Expect pins in the river and polygons that cover the whole town; plan an outlier pass before analysis (Alderton et al. 2026).
- **Results that vanish kill the next round.** Participants disengage when their role is purely informational (Brown and Kyttä 2014). Say on the first page what happens with the answers, and publish the results where respondents can find them.

## When you build it

The first pin is [Add a map question](/how-to/add-a-map-question/); the attributes on it are [Add sub-questions](/how-to/add-sub-questions/); the existing infrastructure beneath the map is [Add a reference layer](/how-to/add-a-reference-layer/). To keep required fields minimal while still asking follow-ups, see [Make a question conditional](/how-to/make-a-question-conditional/). The wording of the questions themselves is the next essay, [Writing questions people can answer on a map](/learn/writing-map-questions/).
