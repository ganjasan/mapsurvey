# Design: respondent-shared-map

## Context

`overlay-features` (#155, merged 2026-09-05) made a reference layer a container of
`LayerObject` rows owned by the canonical survey, derived its GeoJSON from them
(`layers.rebuild_layer`), served it through `survey_layer_geojson` (ETag on
`updated_at`, `Cache-Control: private, max-age=300`) and the per-object card through
`survey_layer_object`. An "Objects on the map" question (`layer_objects`) binds a layer;
its sub-questions are answered per object into `Answer.layer_object` with a partial unique
constraint; `object_stats.object_aggregates` feeds the Responses per-object table, the ZIP
export and the public `objects` block. The respondent JS (`layer_objects_block.html`)
lists the layer's features, opens the object popup, keeps answered state.

Geo answers are stored by the section POST in `survey_section`: it deletes the section's
top-level answers for the session and re-inserts them (`Answer.id` changes on every
re-submit), one `Answer` per drawn feature, sub-answers under `parent_answer_id`.

Clean sessions (`public_results.EXCLUDED_VALIDATION_STATUSES`, `is_deleted`) define whose
answers count everywhere aggregates are read.

Mockups: `shared-map.mockup.html` (layer card + section list, respondent map + popup,
Responses moderation). Decisions taken with the owner on 2026-09-05 are marked *(owner)*.

## Goals / Non-Goals

**Goals**
- A respondent sees other respondents' marks on the same map where they place their own,
  and can 👍/👎 and comment on one instead of duplicating it.
- Zero new respondent mechanics: the object popup, answered state, `min_objects`, per-object
  results, export and public block from #155 are reused verbatim.
- The creator builds it from first-class pieces — a layer from answers plus an ordinary
  Objects question — and can arrange them across sections *(owner)*.
- Moderation that a three-person parish council will actually use: live by default,
  per-item hide, approve-first as an option *(owner)*.
- Tallies visible by default, others' comments hidden by default, both per-layer settings
  *(owner)*.

**Non-Goals**
- Reactions on the public results page; a threaded comment feed; notifications.
- Respondent identity — reactions stay session-scoped, one per session per object.
- Reactions on marks across *different* surveys.

## Decisions

### D1. A `question` layer is an ordinary `SurveyMapLayer` with a source

```python
class SurveyMapLayer:
    source = CharField(choices=[('upload','upload'), ('question','question')], default='upload')
    source_question_code = CharField(max_length=..., blank=True, default='')
    show_tallies  = BooleanField(default=True)
    show_comments = BooleanField(default=False)
    approve_first = BooleanField(default=False)
```

The source is a question **code**, not a FK. Layers belong to the canonical survey and are
borrowed by versions and draft copies (#155 D-3); question rows are copied per version with
new ids but keep their code. Matching answers by code across `versioning.family_ids`
is what `PublicResultsService` already does. A FK to one version's row would break the
moment a draft is published.

Everything else about the layer is unchanged: color, label, `hidden_layers` per section,
render order, the kill switch, the `questions` binding. The object editor opens read-only
for `question` layers (objects are answers, edit the answer instead).

*Rejected*: a separate `AnswerReaction` table. It would need its own popup, its own
export, its own aggregates and its own public block — every piece #155 already has.

### D2. Objects are materialised, keyed by session and mark index

`LayerObject` gains `status` (D5), `source_answer` (FK `Answer`, `SET_NULL`) and
`source_session` (FK `SurveySession`, `CASCADE`). After the section POST has stored the
geo answers of a source question, `layers.sync_question_layer(layer, session)` runs:

- key = `s<session_id>-<n>` for the n-th feature of that session's answer to the source
  question, in stored order;
- title = the label sub-answer (layer `label_field` names a sub-question code; text, or the
  choice label) truncated to 255, else `''`; category = `''`; geometry from the answer;
- existing objects with the same key are **updated** (geometry, title, `source_answer`),
  missing indexes are created (status per D5), surplus keys of that session are deleted;
- then `rebuild_layer`.

Why not key by `Answer.id`: the section POST deletes and re-inserts answers on every
submit, so a respondent pressing Back and Next would get new ids, the CASCADE would drop
the object, and with it every reaction other people had already left on it. The
session+index key survives a re-submit; only a genuinely removed mark loses its reactions,
which is correct.

Cross-version: `sync_question_layer` resolves the source question in the *session's*
survey by code, so a respondent on an older version still feeds the canonical layer.

### D3. The layer endpoint is per-session for `question` layers

`survey_layer_geojson` for a `question` layer:

- builds the collection from `LayerObject`s with `status='visible'` whose
  `source_session` is clean (not deleted, not `not_approved`/`on_hold`) and is **not** the
  requesting session (`request.session['survey_session_id']`);
- ETag = `layer-<pk>-<updated_at>-<session_id>`, `Cache-Control: private, no-store`.

Rebuilds of `layer.geojson` (the cached text column) still happen for the object editor's
and Responses' map, which show *all* clean objects; the respondent path filters at request
time because "not mine" is per session. Feature count and caps use the clean set.

`layer.updated_at` is touched on every materialisation, moderation action, reaction
submit and session validation-status change, so the ETag and the metadata the shell
receives stay honest.

### D4. Tallies and comments ride the surfaces #155 already has

- Feature properties of a `question` layer carry `tally_up`, `tally_down`,
  `comment_count` when `show_tallies` is on (computed from `object_stats` for the bound
  question's `thumbs` and `text` sub-questions over clean, non-hidden answers). The list
  block renders them as the row's right-hand text, the map as a badge next to the feature,
  the popup card as the tallies line — see the mockup. Off ⇒ properties absent, nothing
  rendered.
- The object card endpoint (`survey_layer_object`) for a `question` layer returns, when
  `show_comments` is on, the newest 10 visible comments (text sub-answers with
  `hidden=False`, clean sessions), quoted, without author. Off ⇒ no `comments` key.
- Tallies are recomputed on every reaction POST (a `rebuild_layer` after
  `_save_object_answers` for bound `question` layers). Layers are capped at 5 000 objects
  and reaction volume is a few hundred per consultation; this stays far from the cost that
  would justify a counter cache.

The bandwagon effect is real (PPGIS literature); `show_tallies=False` is the creator's
answer, not a product default.

### D5. Moderation: status on the object, `hidden` on the comment

```python
LayerObject.status = CharField(choices=visible|pending|hidden, default='visible')
Answer.hidden      = BooleanField(default=False)
```

- New objects are `pending` when the layer has `approve_first`, else `visible`. Flipping
  `approve_first` on does not retro-hide existing objects.
- The Responses tab gets a *Shared map* pane per `question` layer: the per-object table
  from #155 with a Status column, filter chips All / Pending / Hidden, and Approve / Hide /
  Show actions; the row expander lists comments with a Hide/Show each. Hidden and pending
  objects stay in the Responses map, the export and aggregates for the creator — they are
  hidden *from respondents*, not deleted.
- `Answer.hidden` is read by the card endpoint (D4) and by `comment_count`. It is not read
  by export or Responses. It lives on `Answer` rather than a side table because a hidden
  comment is still that session's answer; the flag is meaningless for non-text answers and
  the model comment says so.
- Session status stays the coarse lever: `not_approved`/`on_hold`/deleted sessions drop
  all their marks *and* all their reactions from every read path, via the clean-session
  filter, without touching `status`.

*(owner)*: A+B — live by default with per-item hide, approve-first as an option.

### D6. Assembled by hand: the layer card is the only creator entry point *(owner)*

The Reference layers card in Survey settings gains "New layer from answers": pick a
point/line/polygon question of the survey, optionally the sub-question whose answer labels
each mark, and the layer is created with `source='question'`. Its edit state exposes the
label sub-question, `show_tallies`, `show_comments`, `approve_first`; it has no upload
zone, no draw action, and "Open editor" opens the object editor read-only. From there the
creator adds an "Objects on the map" question bound to that layer wherever they want it —
same section as the geo question for Julian's flow, a later section for "rate what others
said" — with the sub-questions they choose.

Two consequences the editor states plainly:
- With no label sub-question, other people's marks are listed by key (`s12-1`). The card
  says so next to the picker ("Without a label, marks are listed by number"). Choice
  sub-questions are listed before text ones: they cannot carry an address or a name.
- Deleting the source geo question while a `question` layer references its code is
  refused with a message naming the layer, mirroring "bound layer cannot be deleted".
  Renaming the question's code cascades to `source_question_code`.

*Rejected (owner)*: a toggle on the geo question that creates the layer and a pair
question with a 👍/👎 sub-question in one save. It hid three entities behind one checkbox,
needed a refusal path for turning it off, and would have had to invent a "Why here?"
sub-question to give marks a label. A creator who wants the pair builds two questions and
sees exactly what respondents get.

### D7. "Required" is unchanged

The geo question keeps `required`; the pair keeps `min_objects`. A creator who wants
"place a mark OR react to one" sets neither — that is Julian's case. A section-level
"answered = mark or reaction" rule was considered and dropped: it would be the only
cross-question validation in the product, for a case the two knobs already cover.

### D8. Export: the verdict on the author's own feature

`download_data`'s GeoJSON for a source geo question adds per feature `mark_key`,
`votes_up`, `votes_down`, `comments` (count) computed from the bound question's
aggregates over clean sessions, so the council's dog-bin layer opens in QGIS with the
tally on each mark. The per-object `objects_<code>.csv` and `<layer>.results.geojson`
from #155 are produced as for any bound layer. Hidden/pending status is a column in the
per-object CSV (`status`) — the creator's moderation is part of their data.

### D9. Serialization

`serialize_layers` writes `source`, `source_question_code`, `show_tallies`,
`show_comments`, `approve_first`; `question` layers write no objects manifest.
`extract_layers` creates them empty; `_apply_layer_objects_manifest` is skipped for them.
The pair question travels as any question (it already carries `layer` by export index).
An import whose `source_question_code` matches no geo question drops `source` to
`upload` with a report line, the same fail-safe as unresolvable visibility rules.

### D10. Versions and draft copies

Answers on any version feed the canonical layer (D2 resolves by code). Reactions
(`Answer.layer_object`) point at canonical objects regardless of version, as in #155.
`clone_survey_for_draft` does not copy layers (they are borrowed), so nothing new to copy.

## Risks / Trade-offs

- **Per-session endpoint = one DB query per respondent page load** instead of a CDN hit.
  A lecture-hall burst on a shared-map survey therefore costs one `LayerObject` query per
  student; the query is indexed on `(layer, status)` and bounded by the 5 000 cap. If the
  k6 burst (`loadtest/`) shows it, the fix is a 30 s server-side cache of the *clean
  visible* collection with the own-session filter applied in Python.
- **Rebuild on every reaction** touches `updated_at` and rewrites `geojson` for the
  creator surfaces. Fine at hundreds of objects; note it in the layer cap discussion if
  someone runs a 5 000-mark shared map.
- **Label from free text** exposes the author's words to every respondent. The layer card
  lists choice sub-questions before text ones and says which is which; moderation exists
  for the rest.
- **Materialisation inside the section POST** adds a handful of writes to the hot path.
  It runs only for source questions and only after the answers commit; failure there must
  not lose the answers, so it is wrapped and logged, and a later submit re-syncs.
- **Pending objects and `min_objects`**: a respondent can only react to visible objects,
  so a pair question with `min_objects > 0` on an approve-first layer with nothing approved
  blocks Next. The Shared map pane shows a warning when `approve_first` is on, `pending >
  0` and the bound question has `min_objects > 0`.

## Migration Plan

One schema migration: three booleans + two chars on `SurveyMapLayer`, `status` +
two FKs on `LayerObject`, `hidden` on `Answer`. All defaults; no data migration.
Existing layers are `upload`, existing objects `visible`. Rollback = reverse migration;
no environment flag (owner: no new kill switches).

Deploy order: this change after `overlay-features` is archived (its deltas synced), so the
spec tree matches the code the migration extends.

## Open Questions

- Tally badge on the map at high mark density: hide badges below zoom 14 or when more than
  200 visible features, same rule as labels.
