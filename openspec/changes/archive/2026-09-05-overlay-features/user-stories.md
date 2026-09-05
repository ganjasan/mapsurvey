# Overlay features: browse, learn, answer — user stories & journeys

**Epic**: community-engagement — merges backlog #151 (browse the creator's map objects)
and #152 (ask questions about the creator's map objects). Owner decision 2026-09-01:
the two items are one product surface and ship as one change.

**Epic statement (owner, 2026-09-01, translated)**

> As a representative of a city administration I want residents' opinions on the ten
> or so objects currently under construction. I want all objects on one map. When a
> resident clicks an object they get information about it and can answer my
> questions about it and leave their own comments.

**Design partner**: Sarasota MPO (road-segment review — today a workaround with 5
layers + 4 colour-coded pin questions). Competitive reference: PARTIMAP demo
(`docs/marketing/competitors/partimap/03…09`), Ideenkarte like/dislike voting.

**Builds on**: FD-1 `reference-overlay-layers` (spec exists, shipped) — `SurveyMapLayer`
with `key_field` reserved for exactly this.

**Mockups** (next to this file):
- `mechanism-ab.mockup.html` — **the approved one.** Section 0 = editor (approved), A = respondent
  default (approved), B = later alternative view. Comparison table at the end.
- `layer-editor.mockup.html` — **the object editor screen (D9)**: list · map with drawing
  tools · card editor with attachments; empty state; bulk import.
- `editor.mockup.html` — Reference layers card (section 1, now with an "Open editor"
  button) and section list (section 3) stand; section 1b (table inside the card) is
  superseded by `layer-editor`; section 2 (question modal) by `mechanism-ab` section 0.
- `respondent.mockup.html` — list/search/chips and the mobile panel flow still stand; the
  *card in the panel* is variant B and is NOT the default — under A the card is the map popup.

## Decisions (owner, 2026-09-01)

| # | Decision | Consequence |
|---|---|---|
| D1 | #151 + #152 are one change (`overlay-features`). | One spec set, one PR sequence. |
| D2 | "Objects on the map" is a **question type** in the *Map questions* group of the existing picker. | Ordering, translations, visibility rules, duplicate/copy come for free. Resolves former open question 1. |
| D3 | Sub-questions are the **single mechanism** for "ask about an object on the map", shared by geo questions and Objects on the map. Two entry points, one modal: a nested *Sub-questions* list inside the question modal (new, for geo types too) and the existing "Add Sub-question" under the question in the section list. | Question nesting reuses `parent_question_id`. Answer storage for layer objects is still keyed by feature id, never modelled as a sub-answer of a respondent geometry (#152 constraint). Resolves former open question 2. |
| D4 | A geo question **without** sub-questions is a normal case. No blocking, no required minimum; only visual hints (empty Sub-questions list with the geo tip line, one-click add). | Prod analysis of the "separate question after the geo question" habit (`geo_subq_usage.sql`) informs the hint copy, not a gate. |
| D5 | Respondent default = **variant A**: the panel list is navigation (search, chips, ✓, counter); clicking a row or a feature opens the **same Leaflet popup** used on respondent-placed features, with object content + sub-question form + ✓ (no 🗑 ✎ on creator objects). | Reuses `_buildPopupHtml`, `show_popups`, popup sizing; geo flow untouched; `geo-multi-feature-input` spec unchanged. Answers save on ✓ like geo popups. Mobile = today's popup behaviour. Resolves former open question 4. |
| D6 | **Variant B** (card in the panel, also for geo sub-questions) is deferred: to be added later as an **alternative view** the creator can switch to, not a replacement. | Not in this change's specs; noted in the backlog when this change archives. |
| D7 | A reference layer is an **editable table of objects**: per-object card editing (title, category, rich-text description, link) plus **attachments — images, audio, documents, video**. GeoJSON properties only pre-fill the table. | An object becomes an entity, not a GeoJSON row: needs a `LayerFeature`(-like) model keyed by (layer, key) with a content record and an attachment table, instead of stuffing URLs into `geojson` properties. Creator assets go to the **public** artwork tier (respondents must load them without auth); the existing respondent `Upload` model uses the private tier and is NOT reused as-is, but its size caps and MIME checks are. Video = upload with a size cap **or** embed link (YouTube/Vimeo `iframe` is already in the sanitizer allow-list) — decide in design. Closes open question 3; A2 moves into slice 1 and becomes the largest editor piece of the change. Mockup: `editor.mockup.html` section 1b. |
| D9 | The object editor is a **separate full-page screen** (`Survey settings → Reference layers → Open editor`, own URL under `/editor/surveys/<uuid>/layers/<id>/`), not a tab inside the layer card. Three reasons from the owner: not every creator can produce GeoJSON — objects must be **drawn on the map** in the editor; not every creator can host files — attachments are **uploaded**; a layer can hold **hundreds** of objects — the list needs search, filters, keyboard navigation and bulk operations, which a card inside Survey settings cannot carry. | Supersedes the "no new screen" stance and `editor.mockup.html` section 1b (kept as history). Absorbs backlog **FD-17** (`feature-draw-overlay-layer-in-editor`) into this change. Layout: object list · map with Leaflet.draw · object card editor (`layer-editor.mockup.html`). GeoJSON upload becomes one of three ways to get objects in (draw / import GeoJSON / import content CSV), not the entry gate. |
| D8 | **👍/👎 is its own input type `thumbs`**, not a two-option `choice`. | Picker card in *Questions* group; stored as `up`/`down`; export and charts aggregate as for/against; the Ideenkarte like/dislike gap is named by a visible type. Closes open question 5. |

---

## Personas

| Persona | Who | Wants |
|---|---|---|
| **Creator** (Marta) | Planning officer at a city administration; has a GeoJSON of 10 construction sites from the GIS department, plus a photo and a paragraph per site | Publish "what we are building and what do you think" without a developer; read results per site |
| **Respondent** (Anton) | Resident, opens the link from a Telegram channel on his phone; cares about 2 of the 10 sites, has never heard of the other 8 | Find *his* sites fast, understand what is planned, say what he thinks in under 3 minutes |
| **Analyst** (Marta again, two weeks later) | Same officer, now in the Responses tab and in a council meeting | Per-site aggregates: average rating, 👍/👎 counts, the comments — exportable, presentable |

---

## User stories

### A. Creator — putting objects on the map with content (was #151)

- **A0.** As a creator without GIS skills I want to open an **object editor screen** and
  **draw** my objects on the map (point, line, polygon) and fill in each object's card
  right there, so that I never need a GeoJSON file to present my project. *(D9; absorbs
  backlog FD-17.)*
- **A1.** As a creator who does have a GeoJSON I want to import it into the same editor and
  map its properties to **title**, **category**, **description** and **link**, so that the
  object table is pre-filled with what the GIS department already gave me and I re-type
  nothing.
- **A1a.** As a creator with **hundreds** of objects I want the object list to stay usable:
  instant search, category filter, "objects without a photo / description" filters,
  keyboard up/down through the list with the map following, and bulk actions (set
  category, delete selected), so that a 300-stop inventory is editable in an afternoon.
- **A1b.** As a creator I want to bulk-add content — **import a CSV** of title/category/
  description/link matched by key or title, and **drop a folder of photos** matched by
  filename to object title or key — so that content for hundreds of objects arrives in one
  step, not three hundred.
- **A2.** As a creator I want every object to have a **card editor** (title · category ·
  rich-text description · attachments · link · geometry) opened from the list or from the
  map, so that a typo or a missing photo is fixed in place and never forces a re-upload of
  the whole layer. *(D7 + D9 — in scope, slice 1.)*
- **A2a.** As a creator I want to **attach files to an object** — images, audio, documents,
  video — from the card editor, so that a site can carry its rendering, the noise-study
  PDF and a walkthrough clip without me hosting them anywhere.
- **A2b.** As a creator I want the object description to be **rich text** (the same Quill
  as everywhere else, with its image button), so that the card reads like a project page,
  not a database field.
- **A2c.** As a creator I want to **add or remove objects** in the table, not only edit
  them, so that the layer stays current as the programme changes. *(Geometry is still
  drawn/uploaded, not typed; adding a row = draw on the map or import one feature.)*
- **A3.** As a creator I want to place an **"Objects on the map" block** into a section
  and bind it to one reference layer, so that the object list appears in the panel
  exactly where my narrative needs it (after the intro, before the general questions).
- **A4.** As a creator I want the block to show a **search box and category chips** when
  the layer has a category field, so that 40 objects stay navigable; and I want them
  hidden automatically when there are ≤ 5 objects, so that a 3-variant vote does not
  look like a database.
- **A5.** As a creator I want the preview to show the block as respondents will see it
  (list ↔ map linked), so that I can check the photos and the zoom before publishing.

### B. Creator — asking about each object (was #152)

- **B1.** As a creator I want to attach **questions to the block** that respondents answer
  **once per object**, so that "How do you rate this site?" is asked about each of the
  ten sites with a single question definition.
- **B2.** As a creator I want the first per-object question types to be **rating (stars)**,
  **👍/👎**, **single choice**, and **free text (comment)**, so that the two shapes we saw
  buyers use (rate stations, vote between alternatives) plus "leave your comment" are
  all covered.
- **B3.** As a creator I want to set a **minimum number of objects** a respondent must
  answer on (default 0), instead of the ordinary "required" flag, so that "rate the
  sites" never means "rate all ten or you cannot continue".
- **B4.** As a creator I want to mark a subset of a layer as **askable** (default: all),
  so that the context features (the district boundary) sit on the same map without a
  star widget.

### C. Respondent — finding and understanding an object (was #151)

- **C1.** As a respondent I want to see **all objects listed in the panel** next to the map,
  with a category and a one-line title each, so that I can scan the ten sites in seconds.
- **C2.** As a respondent I want to **type part of a name** or **tap a category chip** and
  have both the list and the map narrow down, so that I find the site near my home
  without panning.
- **C3.** As a respondent I want to **tap a row** and have the map fly to the object,
  highlight it and open its **card** — under D5 the same map popup used on my own placed
  features — with photo, text and a "more on the city website" link, so that I learn what
  is planned there.
- **C4.** As a respondent I want to **tap the object on the map** and get the same card,
  with the matching row highlighted in the list, so that either entry point works and I
  never lose my place.
- **C5.** As a respondent placing my own point/line/polygon in another question, I want
  taps on the map to place geometry, **not** open object cards, so that the objects
  never get in the way of answering.
- **C6.** As a respondent on a phone I want the panel to slide away to show the map (the
  arrow the survey already has) and the object card to open as the same near-full-width
  popup my own placed features use, so that nothing new has to be learned on mobile.

### D. Respondent — answering about an object (was #152)

- **D1.** As a respondent I want the object card to contain the creator's sub-questions
  (stars / 👍👎 / choice / comment) and to save my answers with the popup's **✓** exactly
  like on my own placed features (closing the popup also keeps what I typed, as today), so
  that I can rate three sites and move on without hunting for a separate Save button.
- **D2.** As a respondent I want answered objects **visibly marked** in the list (tick,
  muted) and on the map, and a counter "Answered 3 of 10", so that a long list feels
  finishable and I can see what I skipped.
- **D3.** As a respondent I want to **change** an answer by reopening the card, so that a
  mis-tap on a star is not final.
- **D4.** As a respondent I want the Next button to tell me if the creator requires a
  minimum ("Please rate at least 1 site") and to let me continue otherwise, so that I am
  never trapped by objects I do not care about.

### E. Analyst — reading the results

- **E1.** As an analyst I want the Responses tab to show **per-object aggregates** (mean
  stars, 👍/👎 counts, answer count, comments list) with the object highlighted on the map
  when I pick it, so that the council meeting gets "site 7: 4.2★, 31 votes" not a CSV.
- **E2.** As an analyst I want the ZIP export to contain a **CSV keyed by object id** with
  one row per (session, object) and the creator's layer GeoJSON **enriched with
  aggregates** per feature, so that the GIS department can style the result map
  themselves.
- **E3.** As an analyst I want per-object aggregates on the public results page to respect
  the existing **k-anonymity mask**, so that "1 vote on site 3" never identifies a
  neighbour.

---

## User journeys

### J1 — Creator: from GIS file to published consultation (Marta, ~20 min)

1. Creates a survey from the wizard; intro section says what the city is building.
2. **Survey → Map layers → Upload** `construction_sites_2026.geojson` (10 polygons,
   properties `name`, `type`, `photo`, `about`, `url`). Upload returns the property
   names; she maps title=`name`, category=`type`, image=`photo`, description=`about`,
   link=`url`. Colour: city orange. *(Existing FD-1 upload screen, four new dropdowns.)*
3. Opens the intro section, adds block **"Objects on the map"**, picks the layer. Preview
   shows the list; she clicks "Ring road overpass" and the map flies there — the photo
   the GIS colleague attached shows up.
4. In the block she adds three per-object questions: *"How do you rate this project?"*
   (stars), *"Should the city build it?"* (👍/👎), *"Your comment"* (text). Sets "at least
   1 object" — she wants everyone to engage with something.
5. Adds a normal section after it: "About you" (district, age band).
6. Publishes; the share link goes to the district Telegram channels.

**Failure branches**: the GeoJSON has no `photo` for 3 sites → card shows no image, no
error; the `url` property is missing entirely → the link dropdown stays empty, that is
fine. A `<script>` in `about` → `coerce_creator_html` strips it, like every other
creator field.

### J2 — Respondent on a phone: two sites out of ten (Anton, ~3 min)

1. Opens the link; panel covers the map (existing 88 % overlay). Reads two sentences of
   intro, scrolls to **"Objects on the map (10)"** with a search box and chips *Roads ·
   Parks · Schools · Utilities*.
2. Taps chip **Parks** → list shrinks to 3; taps the ▶ arrow to hide the panel → map shows
   the 3 parks highlighted, the other 7 dimmed.
3. Taps the park polygon nearest his home → the map popup opens (near-full-width, as on
   his own placed points): photo, "New pocket park on Lenina 14, 0.4 ha, opening 2027",
   link.
4. Below the text: ★★★★☆ (he taps 4), 👍, and a comment box — types "Please keep the
   old oaks". Taps **✓** → the popup closes and the answers are kept.
5. Opens the panel (◀) → the park row is ticked and muted; counter "Answered 1 of 10".
   Clears the chip, searches "school", taps "School №12 extension" → map flies there,
   popup opens; rates 2★, 👎, comment "The street cannot take more traffic", ✓.
6. Taps **Next** → allowed (min 1 met). Answers "About you", finishes. Total: 2 objects,
   6 answers, ~3 minutes.

**Failure branches**: he taps the map while a *different* question's point-placement is
active → the tap places the point; popups do not open (C5). He closes the popup with ×
instead of ✓ → the typed values are kept anyway (today's geo-popup behaviour); nothing is
lost, and the row still shows ✓.

### J3 — Analyst: results for the council (Marta, two weeks later)

1. **Responses → Map** shows the layer with a badge per site: "31 · 4.2★ · 👍 24/7".
2. Clicks site 7 → the side table filters to that site's 31 rows; comments readable
   in-line, exportable.
3. **Download ZIP** → `objects_answers.csv` (session, object_id, object_title, question
   code, value) + `construction_sites_2026.results.geojson` (original features +
   `answers`, `rating_mean`, `up`, `down`).
4. Public results page: a per-site bar chart of mean rating; sites with < 3 answers
   masked, as elsewhere.

---

## Scope split — what ships together, what can trail

| Slice | Stories | Ships |
|---|---|---|
| **1. Objects editor** | A0, A1, A2, A2a–A2c | the new screen (D9): draw / import, card editor, attachments. Own PR — useful on its own for FD-17 |
| **1b. Browse** | A1a, A1b, A3, A4, A5, C1–C6 | list block for respondents + scale features for hundreds of objects |
| **2. Answer** | B1–B4, D1–D4 | same change, second PR; the buyer ask |
| **3. Read** | E1–E3 | closes the loop; export E2 must not slip — data without export is a demo |
| Later | bulk content import (ZIP with an assets folder), variant B view (D6) | after real creators show the need |

---

## Open questions (for the owner, one at a time)

All five original questions are closed (D2, D3, D5, D7, D8). None open.
