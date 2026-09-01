# Feature-anchored answers — respond *about* a reference feature, not near it

**Type**: feature
**Priority**: high
**Area**: fullstack
**Created**: 2026-09-01
**Epic**: community-engagement

## Description

Today a reference layer is scenery: respondents see it, at best tap a feature for a read-only
popup, and then answer by placing their *own* geometry beside it. For a whole class of surveys
that is the wrong primitive. The creator already has the objects — road segments, parcels,
trees, bus stops, plan elements — and wants respondents to **pick one of them** and say
something about it: rate it, classify it, comment on it, vote for it. The answer should be
"segment #4711: possible false positive, because …", not "a point at 27.33,-82.53 that is
probably about the magenta line next to it".

### The case that surfaced it (2026-09-01)

**Sarasota/Manatee MPO — Asset Prioritization Map** (creator `mrgmiami`, published
2026-08-28, 60 sessions, 12 geo answers). Five reference layers: four *Priority Score* classes
of road segments (6 119 segments carrying `priority_score`, `priority_class`, simplestyle
colours) plus the county boundary. One map section with **four point questions used as
category buckets** — *Green: Matches our experience*, *Red: Possible false positive*,
*Yellow: Missed asset*, *Purple: Fixed or programmed* — each with a text sub-question
"Please add any relevant details about this location." The section text tells respondents to
use the Layers panel to toggle score classes while reviewing.

What the MPO actually wants is a **feature review**: for a given scored segment, does the
model match local experience? The pins are a workaround with three costs:

1. **No join.** A pin carries no segment id; the analyst has to spatially join pins to the
   segment network afterwards, and a pin dropped between two parallel segments is ambiguous.
2. **The category is smuggled into the question type.** Four point questions exist only to
   colour-code one categorical answer; the export has four geometry columns for one question.
3. **Placement friction.** On a 6 000-segment network the respondent must zoom in enough to
   drop a pin *on* the segment they mean, on a phone. Tapping the segment itself is what they
   expect — it is how every map app behaves.

The same shape appears in earlier leads: per-zone assessments (volunteer counting zones,
Olney), parcel-level feedback (planning consultations), "which of these proposed sites do you
prefer" (participatory budgeting on Maptionnaire/Social Pinpoint, where "comment on a plan
element" is a headline feature we lack).

## Proposed UX

**Creator (editor)**

- A geo question gets a new answer mode next to *place / draw*: **"pick from layer"**. The
  creator selects one reference layer (or several) and the layer's **key field** — the
  `SurveyMapLayer.key_field` column reserved for this since FD-1 — plus optional display
  fields shown to the respondent when a feature is selected (name, score, description).
- Sub-questions of that geo question become the per-feature form, exactly as sub-questions
  already are the attributes of a placed point ([[architecture-subquestions-geojson]]): a
  `choice` (Matches / False positive / Missed / Fixed), a `text` comment, a `rating`.
- Optional: *allow several features per response* (already how multi-geometry works) and
  *one answer per feature per session* (no double voting on the same segment).

**Respondent**

- Features of a pick-from layer are interactive: hover highlight, tap selects (thick outline),
  a card/popup shows the creator-chosen display fields and the sub-question form. Submit
  attaches the answer to that feature; the feature gets a "answered" style so the respondent
  sees what they have done. Deselect by tapping again.
- "Missed asset" — the one case where the object does *not* exist yet — stays a regular
  *place a point* question. Mixed surveys are the norm, not the exception.
- Mobile: tap targets on thin lines are the known hard part; use a generous
  `L.polyline` hit tolerance / an invisible wider hit-line beneath, the way GIS viewers do.

**Results (Responses tab, public results, export)**

- Answer stores `layer_id + feature_key` **and** a snapshot of the feature geometry (layers
  can be re-uploaded; the answer must still draw after that). Export: a GeoJSON per
  pick-from question whose features are the *picked reference features* with the
  sub-answers as properties, plus `feature_key` in the CSV — the join is free.
- Responses Map pane: pick-from answers render as the highlighted reference feature (it is
  already on the map as a reference slot); aggregate view — "this segment got 7 false
  positives, 2 matches" — is a choropleth over the layer by answer count / dominant class,
  which is a natural public-results block too.

## Data model sketch

- `Answer.reference_layer` (FK, PROTECT-safe: nullable, layer deletion warns like question
  deletion does) + `Answer.reference_feature_key` (str) + geometry snapshot in the existing
  geo columns (a line answer for a line feature, polygon for polygon, point for point) — the
  existing geometry fields keep every downstream consumer (export, analytics, public results)
  working unchanged.
- `Question.answer_mode = place | pick` and `Question.pick_layers` (M2M or JSON of layer ids).
- Key field required on a pick-from layer; upload validation already returns the property
  union so it is a dropdown. Uniqueness of the key within the file is validated at upload.

## Scope sketch (what a first release needs)

1. Editor: answer mode toggle, layer + key/display field pickers, lint "pick-from layer
   without key field".
2. Respondent: interactive pick-from layer, selection card with the sub-question form,
   answered-state styling, per-feature answer submission over the existing sub-question
   plumbing.
3. Storage + export + Responses map + ZIP round-trip (layer ids remap on import exactly as
   `hidden_layers` does).
4. Later: choropleth aggregate block on public results, one-answer-per-feature rule, voting
   ("like this proposal") as a zero-sub-question variant.

## Non-goals

- Editing reference geometry by respondents (that is field GIS, FD epic).
- Replacing place/draw questions — both modes coexist on one section.
- Image overlays as pick targets (no features to key on; see #147).

## Open questions

- One geo question with a `choice` sub-question, or four "colour" questions as today? The
  proposal assumes the former and needs an editor-side migration story for surveys like
  Sarasota (an AI-assisted "convert these four questions into one with a category" is
  plausible).
- Line hit-testing on touch: prototype before committing to a mobile promise.
- Should `key_field` be optional with a fallback to feature index? Index breaks on re-upload;
  the proposal says required.

## Notes

- `SurveyMapLayer.key_field` help text already reads "reserved for answer-driven map context.
  No UI consumer yet" — this item is that consumer. FD-1 (#reference overlay layers) and
  `responses-reference-layers` (Responses tab, Layers panel, opacity/order) are prerequisites
  and are done.
- Sarasota survey is imported on the dev stand (`10e9e7e0-c1db-4016-9e36-2476fb2bdf2d`) with
  its real layers for prototyping; the creator is a live, paying-shaped B2G lead (an MPO
  running a formal asset-prioritisation review).
- Competitive: Maptionnaire "comment on a plan element", Social Pinpoint "ideas on features",
  Citizen Space geo-consultation — all expose feature-level feedback; none of them export
  the join as cleanly as a GeoJSON of picked features would.
