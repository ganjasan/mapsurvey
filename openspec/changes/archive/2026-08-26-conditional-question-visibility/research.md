# How other survey platforms do conditional logic — competitive research

Date: 2026-08-25. Three parallel research passes over official docs: mainstream form
builders, professional/research tools, geo/participatory platforms. Full source URLs at
the bottom of each section.

## The two architectures

Every platform falls into one of two families (or offers both):

1. **Navigation-based (skip/jump)** — "when answer = X, jump to question/page/section Y".
   Google Forms, Microsoft Forms, SurveyMonkey classic, Typeform, Citizen Space,
   Maptionnaire page jump. Always forward-only (loop prevention), always evaluated on
   the Next click, authored as per-answer-choice → destination maps.
2. **Visibility-based (show/hide, "relevance")** — "this question/section is visible when
   condition C holds". LimeSurvey, ODK/KoboToolbox, Qualtrics Display Logic, Alchemer
   Question/Page Logic, Tally, SurveyMonkey Advanced Branching, Survey123,
   EngagementHQ conditional logic, Maptionnaire branching logic (~2025).

**The professional tools that offer both explicitly steer authors toward visibility and
away from jumps** (Qualtrics: display logic for questions, branch for blocks, skip "only
within a block"; Alchemer: "prefer show-logic, keep skip/disqualify at a minimum").
Navigation-only platforms (Google, Microsoft) are also the #1 complaint generators:
choice-only triggers, no in-section logic, section explosion, broken progress bars,
back-button leaking answers from abandoned branches.

## Section/group level is table stakes — and it is the SAME mechanism

- **LimeSurvey**: relevance equation on the question AND on the group; the two are
  **ANDed**. A group whose relevance is false = the whole page is skipped in navigation.
- **ODK/XLSForm** (Survey123, Kobo): `relevant` on any row, including `begin_group` — a
  group hides/shows as a unit, relevance propagates to children.
- **Alchemer**: Question Logic + Page Logic, same rule builder; the docs recommend
  grouping co-conditioned questions onto one page and conditioning the page.
- **Google Forms**: the ONLY branching primitive is section-level ("go to section based
  on answer") — the mass-market user's default mental model of branching is sections.

Conclusion for us: a visibility rule must attach to **either a question or a section**,
one rule shape, one evaluation engine. Section hidden ⇒ skipped by next/prev navigation.
This fits our `next_section_id` linked list far better than jump-targets would: we never
store "go to X", we just skip non-visible sections while walking the list — Back keeps
working, loops are impossible by construction.

## Consensus semantics (adopt as-is)

| Rule | Who |
|---|---|
| Hidden ⇒ value cleared / not submitted, enforced server-side | LimeSurvey (NULLs in DB), ODK (omitted from submission XML), universal "no platform submits answers to questions never seen" |
| `required` enforced only on visible questions | Universal, no exceptions ("skip logic takes precedence over mandatory" — Kobo) |
| Cascade: if the controlling question is itself hidden, dependents are hidden | LimeSurvey cascading relevance, ODK, EngagementHQ (nested conditionals; deactivate parent ⇒ children deactivate) |
| Condition drivers restricted to closed single/multi choice in v1 | The floor everywhere: Google/MS/Citizen Space = radio/dropdown only; multichoice via `selected()` any-of semantics (ODK), "is one of the following" (Alchemer) |
| Evaluation live on the page (not only on Next) when the controlling question is on the same section | EngagementHQ ("takes effect immediately"), Tally, Maptionnaire branching, Survey123 |

Notable divergence: **Survey123 makes clear-vs-keep a per-rule creator option**
(`relevant` = discard vs `bind::esri:visible` = hide but submit). v1 picks discard
(the research-tool consensus and the data-integrity fix); the option is a documented
possible future.

## The export three-state problem

Qualtrics is the only one that solves "not shown" vs "shown but unanswered" cleanly:
export option recodes seen-but-unanswered as `-99`, never-displayed stays blank.
ODK/Kobo/LimeSurvey collapse both into blank. **The distinction cannot be reconstructed
after the fact** — whether a question was displayed must be recorded at collection time.
Minimal v1: we can compute displayed-ness deterministically from the stored answers +
rules (our rules are pure functions of recorded answers), so we do NOT need to store
per-question display state — worth stating in design.md explicitly.

## Known bug classes to design out

- **Google Forms back-button leak**: respondent goes back, changes the controlling
  answer, answers on the abandoned branch are still submitted. This is exactly our
  Sodankylä contradiction. Fix = server-side discard of non-visible answers at submit.
- **SurveyMonkey checkbox first-match trap**: multi-select where several checked options
  carry conflicting jump rules — first match silently wins. Avoided entirely by
  visibility semantics (any-of match, no destinations to conflict).
- **MS Forms reorder breakage**: reordering questions silently breaks branch targets.
  Our editor must surface orphaned rules (controlling question deleted/moved after the
  dependent, option removed) instead of silently dropping them.
- **Progress bars**: "nobody solves this well" — Google officially says don't use a
  progress bar with skip logic. Our `survey-progress` count must be per-respondent
  dynamic, or at minimum exclude never-visible items.

## Map × logic: FD-14 is confirmed white space

No platform productizes answer → map context (extent/overlay filter/basemap). Survey123
explicitly cannot (community-confirmed). Closest: Maptionnaire conditional styling
(cosmetic restyle of the respondent's own pins by a prior answer), Citizen Space
Geoselect (map answer drives page routing — the inverse direction). Keeping FD-14 as a
separate change is correct; it is a differentiator, not parity work.

## Per-platform quick reference

| Platform | Question-level | Section/page-level | Rule drivers | Hidden answers |
|---|---|---|---|---|
| Google Forms | — | ✅ only mechanism | single choice/dropdown | leaked on back-nav (bug) |
| MS Forms | ✅ jump | ✅ | single choice only | not submitted |
| Typeform | ✅ jump (= hide, 1-q-per-page) | — | rich: all types, and/or | not submitted |
| SurveyMonkey | ✅ skip + show/hide (paid) | ✅ | closed-ended; AND xor OR | marked "skipped" in Analyze |
| Qualtrics | ✅ Display Logic | ✅ Branch (blocks) + Skip (in-block) | anything + embedded data, and/or groups | blank; -99 export recode |
| LimeSurvey | ✅ relevance | ✅ group relevance (ANDed) | full expression language | NULLed in DB |
| ODK/Kobo | ✅ `relevant` | ✅ on `begin_group` | XPath expr; UI builder compiles to it | omitted from submission |
| Alchemer | ✅ Question Logic | ✅ Page Logic | per-type operators, and/or groups | not submitted |
| Survey123 | ✅ rules/expr builder | ✅ groups/pages | multi-criteria and/or | **per-rule choice: discard or keep** |
| Maptionnaire | ✅ branching (~2025) | ✅ page jump | choice-based | undocumented |
| Citizen Space | — | ✅ page skip only | radio/dropdown/yes-no/matrix; NOT text/multi-select | undocumented (forward-only) |
| EngagementHQ | ✅ conditional (nestable, live) | ✅ skip logic (dropdown/radio) | closed single-choice | undocumented |

## Source URLs

Mainstream: https://support.google.com/docs/answer/141062 ·
https://help.typeform.com/hc/en-us/articles/360029116392 ·
https://www.typeform.com/developers/create/logic-jumps/ ·
https://help.surveymonkey.com/en/surveymonkey/create/question-skip-logic/ ·
https://help.surveymonkey.com/en/surveymonkey/create/advanced-branching/ ·
https://support.microsoft.com/en-us/topic/dd443878-959b-4379-8016-39f885c0ae6b ·
https://tally.so/help/conditional-form-logic

Professional: https://www.qualtrics.com/support/survey-platform/survey-module/using-logic/ ·
https://www.qualtrics.com/support/survey-platform/survey-module/question-options/display-logic/ ·
https://www.qualtrics.com/support/survey-platform/data-and-analysis-module/data/download-data/export-options/ ·
https://www.limesurvey.org/manual/ExpressionScript_-_Presentation ·
https://www.limesurvey.org/manual/QS:Relevance ·
https://help.alchemer.com/help/getting-started-logic ·
https://docs.getodk.org/form-logic/ · https://xlsform.org/en/#relevant ·
https://community.kobotoolbox.org/t/skipping-mandatory-questions/35979 ·
https://forum.getodk.org/t/include-non-relevant-groups-and-fields-in-odk-central-api-responses/33536

Geo: https://doc.arcgis.com/en/survey123/create/web-designer/webdesigneressentials.htm ·
https://www.esri.com/arcgis-blog/products/survey123/announcements/whats-new-in-arcgis-survey123-november-2023 ·
https://community.esri.com/t5/arcgis-survey123-questions/dynamically-setting-initial-geoshape-map-extent-by/td-p/1497172 ·
https://support.maptionnaire.com/hc/en-us/articles/360015045940-Page-jump ·
https://help.delib.net/article/305-skip-logic-a-quick-start-guide ·
https://help.delib.net/article/1371-accessible-skip-logic-with-geoselect ·
https://helpdesk.bangthetable.com/en/articles/3292135-compare-conditional-and-skip-logic ·
https://learn.socialpinpoint.com/form/form-logic
