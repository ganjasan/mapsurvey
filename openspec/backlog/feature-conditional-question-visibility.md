# Conditional question visibility

**Type**: feature
**Priority**: very high
**Area**: frontend
**Created**: 2026-03-30

## Description

Allow survey creators to define skip/branching logic so that questions are shown or hidden based on previous answers. For example, show question 7 only if the respondent answered "yes" to question 6. This is a core survey feature commonly known as conditional logic or skip logic.

## Second confirmed case — Sodankylä light-pollution study (2026-08-17)

`mariaalatalo` / maria.alatalo@sodankyla.fi, Sodankylä municipality (Finland). Survey 404
"Valosaastekysely asukkaille ja sidosryhmille" (`b61ec821-8356-4307-a9f0-d2366ba30fe0`),
published, open 2026-08-06 – 2026-09-27, part of the grant-funded **LOISTAVA** project. 12
sections, 41 questions, 24 sessions and 4 completions at the time of writing.

**The author is already writing the branching by hand, into the question text.** Three questions
begin with *"Mikäli…"* ("if you are / if you have noticed…"), which is what an author does when
the product cannot express the condition:

| Trigger question | Answer | What is shown anyway |
|---|---|---|
| `Toimitko matkailualan yrittäjänä?` | **"En" — 10 of 11** | `Mikäli toimit matkailualan yrittäjänä, mitä palveluita yrityksesi tarjoaa?` shown to all 11; **filled in 0 times** — 11 empty answer rows |
| `Oletko huomannut muutoksia?` | "En ole" / "En osaa sanoa" — 2 of 10 | two "if you have noticed…" follow-ups shown to both |
| `Oletko havainnut häiriövalon lähteitä?` | "En" + "en ole kiinnittänyt huomiota" — **4 of 7** | `Mikä havaitsemassasi häiriövalossa häiritsee eniten?` shown to all — and answered **4 times against 3 respondents who said "Olen"** |

That last row is a **data-integrity** consequence, not a UX one: a respondent who stated on the
previous screen that they had noticed no obtrusive light still recorded what bothers them most.
This feeds a municipal `valonhallintasuunnitelma` (light management plan).

### Section-level skip is the expensive half

Section 5 asks respondents to rate **nine named neighbourhoods** (Kiviharju, Kaanaanmaa, Luosto,
Tankavaara, Kakslauttanen…), **all nine required**. The demographic question `Missä asut?` already
knows the answer: **4 of 11 chose "Asun muualla"** (live elsewhere), 1 more only owns a holiday
home. The rating scale does offer "En osaa sanoa", so this is not a missing-option problem — it is
what forcing the full grid does to the data:

```
session 5857:  5 5 5 5 5 5 5 5 5     ← "don't know" nine times, to get past the screen
session 6272:  2 5 3 2 5 5 3 5 5
session 6300:  5 5 4 3 5 5 4 4 2
session 6376:  4 5 5 3 5 5 2 2 5
                                     (5 = "En osaa sanoa")
```

**25 of 63 cells are "don't know" — 40% of the matrix.** For Kakslauttanen it is 4 of 7. The
funnel confirms the cost: section 5 is the only mid-survey step that loses respondents
(9 viewed → 7 submitted); everything from section 6 to 11 holds at 7/7.

## Notes

- Requested by: bisq (geography student)
- The existing sub-question (parent_question / parent_answer) model may serve as a partial foundation, but full conditional visibility across arbitrary questions is a new capability
- Should work within the same section and ideally across sections
- **Real case (Lyon transit survey, bisqunours, 561 sessions):** Question "SI HABITANT DU 8E SEULEMENT: improvement suggestions for 8th arrondissement" is visible to all 98 respondents, but only ~16 selected arrondissement 8. Need: show question X only if answer to question Y = value Z
- **Two halves, worth splitting.** (a) *Question-level `show_if`* — closes every "Mikäli…" case
  above, needs no navigation changes, and is where both confirmed cases hurt most. (b)
  *Section-level skip* — sections are a linked list (`next_section_id` / `prev_section_id`), so
  conditional routing has to sit on top of that without breaking Back or orphaning answers
  already collected in a published survey. Ship (a) first.
- **Both confirmed cases are institutional users with funded, deadline-bound projects** (Lyon
  transit; Sodankylä LOISTAVA, closing 2026-09-27). Same pattern as
  [multi-geometry discoverability](improvement-multi-geometry-discoverability.md): the author
  absorbs the gap silently, writes the workaround into the question text, and never reports it.
- Sodankylä's survey is **live until 2026-09-27**. If (a) lands before then, whether an existing
  published survey can adopt a rule without invalidating already-collected answers becomes a real
  question, not a hypothetical one.
