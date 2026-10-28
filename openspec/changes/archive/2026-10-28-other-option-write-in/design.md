## Context

A `choice`/`multichoice` question stores its options inline (`Question.choices`, a list of
`{code, name}` dicts validated only for those two keys) and its answer as `selected_choices`
(int codes) on an `Answer` row whose `text` column is unused for these types. The respondent
form builds stock Django `RadioSelect` / `CheckboxSelectMultiple` fields (or the custom
`ChoiceDropdownWidget`); the same form's `as_p()` output is cloned into every Leaflet popup
for geo sub-questions and Objects-on-the-map cards, where restore and serialisation are
generic by input `name`. Answers are written at three sites in `views.py` (top-level, geo
feature properties, `obj__<key>__<code>` fields) and read by export (`_answer_cell`), three
Responses formatters in `analytics.py`, `public_results.py` and `object_stats.py`.

## Goals / Non-Goals

**Goals:** one flag on one option; a write-in field under it on every surface the option
renders; text stored with the selection; adjacent export column; inline display for the
creator; no text on public surfaces; revisit restores it everywhere.

**Non-Goals:** visibility rules inside popups (separate backlog item); AI drafts emitting the
flag (strict structured-output schema, follow-up); a per-language placeholder for the field
(the option label is translatable, the placeholder is a UI string); rating/range/ranking/thumbs.

## Decisions

**Text on the same `Answer` row, in `Answer.text`.** One row per (session, question[, feature |
object]) already exists; a second row would need a new relation and every reader would have to
join it. `text` is null on choice answers today, so no migration and no ambiguity: the
storage rule is "text is meaningful only when the flagged code is in `selected_choices`", and
`other_option.other_text(question, codes, raw)` is the one function that applies it at all
three write sites. *Alternative rejected:* a synthetic child text question — that is the
workaround this change replaces.

**POST/DOM field name `<code>-other`.** The suffix must survive three parsers: the geo loop
(`Question.objects.get(code=key)` on every property key — the suffix is skipped before it),
`_parse_object_fields` (`rest.rsplit('__', 1)` — a hyphen leaves it untouched), and the geo
popup's unquoted jQuery selector `[name=<key>]` — a colon would be a syntax error there, a
double underscore would collide with the object separator. Codes are `Q_<digits>`, so the
suffix cannot collide with a real code.

**The widget renders the field.** `OtherChoiceWidgetMixin` overrides `create_option()` and
`option_template_name` so the flagged option's markup carries the `<input name="<code>-other">`
in a `[data-other-for][data-other-code]` wrapper; `ChoiceDropdownWidget` gets the same mixin
and renders the wrapper under the control. Because the markup is part of `{{ field }}` /
`as_p()`, cards, popups, object cards and the live preview all get it with no per-template
work. *Alternative rejected:* injecting the input from JS by reading `question.choices` —
would need the choices JSON on the client for every surface and would race popup restore.

**One delegated script, hidden = disabled.** `other_option.js` binds `change` on `document`,
resolves the wrapper's controlling inputs by name inside the closest form, and toggles
`hidden` and `disabled` together; it focuses the field on a hidden→shown transition. It runs
on `DOMContentLoaded`, `htmx:afterSwap`, and via `window.syncOtherWriteins(root)` from the two
popup-open handlers, because popup restore sets values without events. Disabling matters
twice: a disabled field never posts, and the Next-button required check counts any
non-empty input as "filled" — a stale write-in must not make an unanswered card pass.

**Export: one adjacent column, always present for a flagged question.** `_answer_cell`
returns `{name: label(s), "name: <option label>": text}` — the dict shape `ranking` already
returns and the CSV/object loops already merge; the GeoJSON sub-question loop learns to merge
it (fixing ranking sub-questions in passing). The column is emitted for every row of the
question, empty when the option was not picked, because the CSV is built by pandas from a
list of dicts and orders columns by first appearance: a column that only exists on some rows
would drift away from its question.

**Display through one accessor.** `Answer.choice_display(lang)` returns `"A, Other: text"`; the
three `analytics.py` formatters call it instead of hand-joining names. `public_results.py`,
`object_stats.py` and `_stats_choices` are deliberately not routed through it — they keep
reading `selected_choices` only, which is the privacy boundary.

**Editor: exclusive checkbox, server clamp.** An "Other" checkbox per row (a checkbox, not a
radio, so a flag can be removed) with a delegated handler that unchecks the others;
`serializeChoices` writes `other: true` on the checked row only; `_guard_choice_codes`, the one
funnel for every save path, keeps the first flag and drops the rest, and the live preview
cleaner does the same. `Question.other_choice_code()` returns the first match, so a stray
double flag from an old ZIP behaves as one.

**`addChoiceRow` becomes a function declaration.** `toggleStarCountField()` runs from the init
block before `window.addChoiceRow = function…` is assigned, which throws and aborts the modal
script for star-rating questions with no rows (PostHog, 2026-09-14). Hoisting the declaration
fixes it without moving code; this change edits that function anyway.

**Restore branches on input type.** `existing_geo_answers` and `_existing_object_answers`
pick the restored value by field presence (`text` before `selected_choices`). With both set on
one row that would restore the text as the choice. Both now branch on `input_type` and add the
`<code>-other` property when the flagged code is selected.

## Risks / Trade-offs

- [A creator flags an option respondents already answered] → nothing changes for stored rows;
  the column appears in the next export with empty cells for old rows. Acceptable.
- [The flag is removed after answers with text exist] → text stays on the rows but is no longer
  displayed or exported; a re-flag brings it back. Documented, not guarded.
- [`Answer.text` on a choice row surprises a future reader] → every reader is keyed by
  `input_type`; `other_option.py` and the model docstring name the rule.
- [Popup HTML is one string per question, cloned per feature] → the wrapper resolves its
  controls by name within the closest form, never by id, so clones stay independent.

## Migration Plan

Deploy; no migration, no data backfill. Rollback is a code revert: rows keep `text`, which
nothing reads once the code is gone.

## Open Questions

None blocking. AI drafts emitting the flag is a follow-up backlog item.
