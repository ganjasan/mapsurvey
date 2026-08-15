---
title: What makes a good map survey — design rules from PPGIS research
created: 2026-08-14
tags: [ppgis, survey-design, research, ai-generation]
---

# Design rules for map-based surveys

The rules a Mapsurvey questionnaire should follow, and the evidence behind each. This
is the shared source for two consumers, so a rule improved here improves both:

- `survey/ai/prompts.py` — the system prompt of the in-product AI draft generator.
- `.claude/skills/newsurvey/SKILL.md` — the assistant skill for hand-building surveys.

Both are operative *summaries*; this file is where the reasoning and citations live.

Note on sources: this file is the only tracked one — the rest of `docs/` is
gitignored on purpose (the repository is public; the heat-domain notes carry
client context, and the source PDFs/EPUBs are other people's copyright). Full
heat/climate notes and the papers themselves live in the main checkout under
`docs/research/ppgis-heat-participation.md` and `docs/papers/`.

---

## Part 1 — What the respondent actually sees

Design rules only make sense against the real interface. A Mapsurvey respondent opens a
page with the questions on one side and a Leaflet map on the other.

- **A section is one screen.** Sections are a linked list; the respondent moves through
  them with Next. Long sections mean long scrolling, not pagination.
- **Geo questions are answered on the map.** The respondent places a marker (`point`),
  draws a path (`line`), or draws an area (`polygon`). One geo question accepts
  **several** features — a respondent can mark five problem spots against one question.
- **Sub-questions of a geo question open in a popup on the feature.** They describe the
  thing that was just marked, and they are the only way to attach attributes to it.
- **Sub-question names become GeoJSON field names on export.** A sub-question called
  "What is wrong here?" becomes that column in the analyst's GIS. Keep them short and
  descriptive; this is the single highest-leverage naming decision in the survey.
- **Non-geo types**: `text` (multi-line), `text_line`, `number`, `choice`, `multichoice`,
  `range` (slider), `rating` (scale strip or labelled list), `datetime`, `image` (upload),
  `html` (a decoration block — it collects nothing).
- **`range` and `rating` derive their scale from the choice codes**, so those codes must
  be integers in ascending order.
- **Multilingual surveys** show the respondent a language picker; every question needs
  content in each declared language or the respondent silently gets the primary one.
- **Export**: one GeoJSON layer per geo question plus a CSV for everything else.

## Part 2 — Design rules and why

### 1. Lead with points; use polygons sparingly

Point mapping is simpler and more effective for lay participants, while polygons cost
more effort per respondent (Brown & Kyttä 2014, citing Brown & Pullar 2012). Our own
funnel agrees: point answer-rate 32%, line 31%, polygon 16.5%, against 40–48% for
non-geo questions. A draft that scatters polygons looks finished and collects nothing.

Match the geometry to the intent (Alderton et al. 2026): **points** for places visited
or things observed, **lines** for routes actually travelled, **polygons** for perceived
extents ("the area I think of as my neighbourhood").

### 2. One mapping task per survey

Every geo question is a separate act of map work. Ask for one, attach sub-questions to
it, and let the respondent add several features if they have more to say.

### 3. Ask what people already do, not only what is wrong

Vienna's heat study enters adaptive behaviours as Block 0 of every regression; subjective
burden stays elevated *even after* adaptation (Seebauer et al. 2024, n=1,983). Without
that block, "not affected" and "coping alone" are indistinguishable — two groups that
need opposite responses. Generalised: ask what the respondent currently does about the
problem, not just whether it bothers them.

### 4. Collect what works, not only what is broken

Plzeň and Olomouc mapped "mental hotspots **and** coolspots"; the planning-relevant
finding was the uneven distribution of the good places, not the bad ones (Lehnert et al.
2023). A survey that only harvests complaints cannot tell anyone what to protect.

### 5. Make access an explicit attribute

A place that costs money, closes early, cannot be reached without a car, or is not
barrier-free is not available to the people a public plan exists to serve (Bochum PPGIS
green-space equity survey, 2025). Where the survey is about a resource, ask about
reaching it, not only about liking it.

### 6. Turn planner assumptions into questions

Citizens in Lehnert et al. suggested water features far less often than planners assume.
When the brief carries an assumption about what people want, phrase it as an option to
be chosen or rejected rather than baking it into the survey's structure.

### 7. Assume weak map literacy and partial local knowledge

PPGIS presumes spatial awareness, digital literacy, map reading, and familiarity with the
place — excluding young children, some older adults, and people new to the area
(Alderton et al. 2026; Laborgne & Klöcker 2023 report exactly this from a Karlsruhe heat
survey). Two consequences for a draft: keep the map task singular and unambiguous, and
make sure the survey still yields usable answers from someone who never touches the map.

### 8. Keep required fields minimal

Self-selected online participation already skews toward the engaged, and internet PPGIS
with random household sampling averages only 13–15% response (Brown & Kyttä 2014).
Required questions that feel like interrogation cost responses from exactly the
harder-to-reach people. In practice: require the mapping task if anything, nothing else.

### 9. Prefer closed answers, but leave one open door

Choice, multichoice and rating questions are answered more often than free text and
aggregate without manual coding. Keep one or two open questions for what the option list
missed — that is where the surprises are.

### 10. Ask only what the creator can act on

Demographics are worth their length only when the results will be segmented by them.
Every question a respondent cannot see the point of is a chance to abandon the survey.

## What the research says will go wrong anyway

Worth telling a client before they discover it:

- **Sampling, not software, is the data-quality problem.** Brown & Kyttä treat sampling
  design as the central determinant of whether PPGIS data can legitimately inform a
  decision.
- **The digital divide excludes the target group.** A heat action plan aims at the
  elderly, ill and isolated — the least likely to answer an online map survey. PPGIS has
  to be one channel among several.
- **Self-reported geometry needs cleaning.** Expect features mapped into water bodies and
  other user error; plan an outlier pass before analysis (Alderton et al. 2026).
- **Results that vanish kill the next round.** Participants disengage when their role is
  purely informational (Brown & Kyttä 2014). Tell people what happens with their answers.

## Sources

- Alderton, A. et al. (2026). *Opportunities and next steps for advancing PPGIS
  methodology in place-based research.* Cities & Health. 10.1080/23748834.2026.2644000 —
  EPUB held locally (not tracked: publisher copyright).
- Brown, G. & Kyttä, M. (2014). *Key issues and research priorities for PPGIS.* Applied
  Geography 46, 122–136. 10.1016/j.apgeog.2013.11.004
- Seebauer, S. et al. (2024). *Feeling hot is being hot?* Sci. Total Environ. 945.
  10.1016/j.scitotenv.2024.173952 — CC BY.
- Lehnert, M. et al. (2023). *Thermal comfort in urban areas on hot summer days and its
  improvement through participatory mapping.* 10.1016/j.landurbplan.2023.104713
- Laborgne, P. & Klöcker, P. (2023). *Exploring PPGIS as a Way of Digital Participation
  on the Example of Heat Relief Planning.* 10.1007/978-3-031-32664-6_15
- Bochum PPGIS green-space equity survey (2025). 10.1016/j.ufug.2025.128989
- Kahila-Tani, M., Kyttä, M., Geertman, S. (2019). *Does mapping improve public
  participation?* 10.1016/j.landurbplan.2019.02.019 — 203 Maptionnaire cases.

Mapsurvey's own answer-rate figures come from the production database (2026-06-10
analysis); domain-specific heat material lives in the untracked research notes (see
the note on sources above).
