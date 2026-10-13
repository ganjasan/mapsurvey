---
title: What participatory mapping is, and when it beats a plain survey
description: Where PPGIS comes from, what a location adds to an answer, and the cases where a map is the wrong tool.
sidebar:
  order: 1
---

A participatory map survey asks people to answer with a place. Instead of "How safe do you feel crossing the main road?" it asks "Mark where crossing is difficult or unsafe", and the answer is a pin, a drawn route or an outlined area, with a few words attached. This essay is about that practice: where it comes from, what the location adds, who uses it for what, and when a map gets in the way of the answer.

## Where the practice comes from

The term *public participation GIS* (PPGIS) dates from the mid-1990s, when geographic information systems were still expert tools and the question was how communities could get a hand on them. The standard review is Sieber (2006), [*Public participation geographic information systems: a literature review and framework*](https://doi.org/10.1111/j.1467-8306.2006.00702.x), which frames PPGIS as the use of GIS to broaden public involvement in policy and to serve the goals of community organisations, and sorts the field by who holds the data, who holds the tools, and what the participation is for.

Two developments turned that framework into something a town can run in a week. One is the Finnish "softGIS" line of work, in which residents mark experiential knowledge, the places they value or avoid, on an online map, and the marks are analysed next to register data (Kyttä et al. 2013, [*Towards contextually sensitive urban densification*](https://doi.org/10.1016/j.landurbplan.2013.01.008)). The other is two decades of place-value mapping in land and conservation planning, summarised in Brown, Reed and Raymond (2020), [*Mapping place values: 10 lessons from two decades of public participation GIS empirical research*](https://doi.org/10.1016/j.apgeog.2020.102156). The reference on methods, sampling and data quality is Brown and Kyttä (2014), [*Key issues and research priorities for public participation GIS (PPGIS)*](https://doi.org/10.1016/j.apgeog.2013.11.004).

A neighbouring tradition is volunteered geographic information: Goodchild (2007) described [citizens as sensors](https://doi.org/10.1007/s10708-007-9111-y), and Haklay (2013) gave citizen science a [typology of participation](https://doi.org/10.1007/978-94-007-4587-2_7), from contributing observations to setting the research question. A wildlife count run on a map survey sits in that tradition; a neighbourhood plan sits in PPGIS. The mechanics are the same.

Be honest about where this sits on the older ladder of participation (Arnstein 1969, [*A ladder of citizen participation*](https://doi.org/10.1080/01944366908977225)). A map survey is consultation: people inform a decision someone else takes. It is not co-decision, and nothing about the map changes that. What it changes is the quality of the information.

## What "where" adds to "what"

A plain survey produces frequencies: 64% of respondents feel unsafe crossing somewhere. A planner cannot act on "somewhere". A map survey produces locations, and locations from many people aggregate into agreement. In the Remington neighbourhood plan survey, 85 residents placed 214 pins for places where getting around is difficult; 20 of them, from 17 different people, landed on one intersection. That is a finding a plan can name. See the [neighbourhood plan](/use-cases/neighbourhood-plan/) case.

The second thing a map adds is specificity without a long question. A single pin with the sub-question "What is wrong here?" carries more than a battery of rating scales about the street network, and respondents tend to answer it, because the place is in front of them. Brown and Pullar (2012) compared points and polygons for mapping place values and found that points yield comparable spatial information at lower cost to the respondent ([*An evaluation of the use of points versus polygons in PPGIS*](https://doi.org/10.1080/13658816.2011.585139)), which is why most map surveys lead with pins.

The third thing is that the map can show the respondent what already exists. Fourteen existing dog-waste bins drawn on the map turned "where should a bin go?" into "where is a gap?", and the pins went into the gaps ([Where to put the bins](/use-cases/where-to-put-the-bins/)). Rall, Hansen and Pauleit (2019) report the same added value in green infrastructure planning: residents locate uses and qualities that an expert inventory does not record ([*The added value of public participation GIS for urban green infrastructure planning*](https://doi.org/10.1016/j.ufug.2018.06.016)).

## Whose places the map collects

Two survey shapes share the same mechanics and need opposite framings. In an **observation** survey, respondents report on the world around them: places visited, problems seen, routes walked. In a **self-registration** survey, respondents put *themselves* on the map, their business, plot or initiative, to build a register. The second kind is written in the second person ("register your enterprise"), collects one main feature per respondent, and its sub-questions describe the respondent's own place. The design rules behind this site record a survey brief for a local-business registry that was drafted in the observer framing ("how often do you buy from local businesses?") and had to be rewritten by hand. If the audience is the thing being mapped, it is a self-registration survey. See rule 2a in [survey-design-rules.md](https://github.com/ganjasan/mapsurvey/blob/master/docs/research/survey-design-rules.md).

## What people use it for

- **Planning consultations.** A town planners' society mapped where people wait, which shortcuts they walk and what to keep around a bus station before a single design was drawn ([Public space microplanning](/use-cases/public-space-microplanning/)).
- **Neighbourhood plans.** A community association asked residents for valued places, places needing attention and places that are hard to get around, as input to a ten-year plan ([Neighbourhood plan](/use-cases/neighbourhood-plan/)).
- **Siting decisions.** A parish council found where bins were missing in nine days ([Where to put the bins](/use-cases/where-to-put-the-bins/)).
- **Campus and student studies.** PPGIS is a standard thesis method; a map survey exports GeoJSON and CSV that go straight into QGIS or R.
- **Citizen science.** A city replaced paper route maps in a wildlife count with pins placed on a phone ([Citizen science count](/use-cases/citizen-science-count/)).

## When not to use a map

A map is a cost. Every map task is an act of work, and respondents skip it more than any other kind of question: on Mapsurvey, point questions are answered by roughly a third of respondents who reach them, polygons by a sixth, against 40–48% for non-map questions. Pay that cost only when the location is the answer. Signs that it is not:

- **The question has no "where".** Satisfaction with a service, budget priorities, how often someone visits: ask these in plain questions, on the same survey if you like, but not on the map.
- **Respondents cannot be expected to know the place.** PPGIS assumes familiarity with the area, map reading and digital literacy, which excludes young children, some older adults and newcomers (Alderton et al. 2026, [*Opportunities and next steps for advancing PPGIS methodology*](https://doi.org/10.1080/23748834.2026.2644000); Laborgne and Klöcker 2023 report this from a heat-relief survey in Karlsruhe, [*Exploring PPGIS as a way of digital participation*](https://doi.org/10.1007/978-3-031-32664-6_15)).
- **The target group is offline.** A heat action plan is for the elderly, ill and isolated, the people least likely to answer an online map. An online map can be one channel, not the only one.
- **The location would identify the person.** "Mark your home" is a disclosure, not a data point. Ask for the area, or do not ask.
- **The location will not be used.** Kahila-Tani, Kyttä and Geertman (2019) reviewed 203 map-survey projects and found that collecting the data was the part that worked; getting it into the plan was the weak step ([*Does mapping improve public participation?*](https://doi.org/10.1016/j.landurbplan.2019.02.019)). If no one will open the GeoJSON, a plain survey is more honest, and the respondent's time is better spent.

When the location is the answer and the audience can give it, a map survey beats a plain survey because it returns something a plain survey cannot: a place that several people agree on, with their reasons attached.

## When you build it

Start with the tutorial at [Start here](/start-here/), which builds a one-map-task survey from an empty workspace. The next essay, [Designing a map survey](/learn/designing-a-map-survey/), sets out the rules and the evidence behind them; [Add a map question](/how-to/add-a-map-question/) is the how-to for the first pin.
