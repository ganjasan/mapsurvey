# Objects on the map — creator journey (proposed, 2026-09-07)

Owner's critique of the current block: four settings of three different owners were
stacked into one "shared map" sub-section, and an uploaded layer never showed it at all.
The journey below gives every setting back to its owner — the **source** (what the layer
is), the **presentation** (how the panel shows it) and the **sub-questions** (what is asked
and what of the answers other respondents see).

## Steps

| # | Creator does | Block shows | Respondent gets |
|---|---|---|---|
| 1 | New Question → "Objects on the map", types a name | **Layer on this map** with an empty picker; status pill *Shows only · collects nothing*; **Ask about each object** empty, with one-tap chips 👍/👎 · Rating · Comment · Other… | nothing yet — no layer, nothing on the map |
| 2a | Picks an **uploaded layer** (existing-dog-bins) | picker shows *· 14 objects*; panel mode List/Legend; search chips (list only); "Respondent sees" draws the panel with the real objects | the layer on the section map, list or legend line in the panel, object cards on tap |
| 2b | Picks **Respondents' marks on Q** instead | a **Source** sub-section appears under the picker: *Label each mark by* [sub-question of Q ▾] · [ ] *Show marks only after I approve them* | other people's marks on the map, labelled by the chosen sub-answer; approve-first hides new marks until moderated |
| 3 | Adds a 👍/👎 sub-question | row *Do you like it · Thumbs* with a switch **Visible to other respondents — shows 👍/👎 counts on each object** (on by default); status pill flips to *Asks about each object*; *Minimum objects* appears | tap an object → 👍/👎 in the popup; counts on the object and in the list |
| 4 | Adds a Comment sub-question | row *Comment · Text* with the same switch (off by default — comments stay private unless the creator opens them) | a comment field in the popup; if opened, other people's comments in the card |
| 5 | Adds a Rating sub-question | row without a switch (nothing shareable yet) | a rating in the popup; results only for the creator |
| 6 | Sets *Minimum objects* = 1 | inline hint "The respondent must answer about at least this many" | the section refuses to move on until one object is answered |

Works the same for an uploaded layer and a marks layer: what other respondents see is a
property of the **sub-question**, not of the layer's source.

## Data

- `Question.share_with_respondents` (boolean) on sub-questions of an Objects question;
  meaningful for `thumbs` (counts) and `text` (comments). Migration: `True` on thumbs
  sub-questions of questions bound to a layer with `show_tallies`, on text ones where
  `show_comments`; the two layer flags are then dropped.
- `SurveyMapLayer.label_field` and `approve_first` stay on the layer — they describe the
  source of a marks layer and are edited under the picker.
- Respondent metadata carries `tallies`/`comments` per layer when any bound question has a
  shared sub-question of that kind; uploaded layers get them attached per request like
  marks layers do today.
