## Context

Two question types render an ordinal scale, and they were built at different times by different
means.

`rating` is a `ChoiceField` with radio inputs. The section template branches on the question type
and picks one of two partials according to `Question.display_style`, falling back to a survey-wide
default in `SurveyHeader.style_settings['rating_display_style']`:

- `rating_scale_strip.html` — a CSS grid of numbered cells, `grid-template-columns: repeat(N, 1fr)`,
  with an anchors row underneath holding the first and last labels, plus a chip showing the current
  selection. The anchors line up because the cells span the container edge to edge.
- `rating_list_pips.html` — one row per choice, each showing the choice's full label.

`range` is an `IntegerField` with `RangeWidget`, a native `<input type="range">` with two sibling
rows built by string concatenation in the widget: anonymous tick marks, and a two-item label row
holding only the first and last choice names.

The alignment defect follows from that construction. `.range-ticks` carries `padding: 0 10px` and
`.range-labels` carries none, so the rows disagree; and neither accounts for the thumb, whose width
(22px) insets the reachable extremes of the track by half that at each end. A label flush to the
element edge points at a value the respondent cannot select.

Constraint that shapes everything below: the save path branches on `question.input_type`, not on
the widget (`views.py:873-878`), so a `range` answer is stored in `Answer.numeric` no matter how it
is rendered. Rendering is therefore free to change without touching storage, export, analytics, or
responses already collected.

## Goals / Non-Goals

**Goals:**

- The slider's ticks and endpoint labels agree with each other and with the thumb's reachable range.
- A creator can show every step's label on a `range` question without us inventing a mechanism for it.
- A `range` answer is stored identically whichever display style is in force, including when the
  style changes mid-collection.
- Existing `range` questions look the same as before, minus the misalignment.

**Non-Goals:**

- Continuous (non-stepped) scales, vertical scales and ranking — backlog #102. Those need new
  widgets and, for ranking, a new answer shape.
- Changing anything about how `rating` renders. The templates are reused as they are.
- A survey-wide default for range styles. `style_settings` currently holds one key,
  `rating_display_style`; adding a parallel key is easy but nobody has asked for it, and per-question
  selection covers the reported need.
- Restyling the slider beyond alignment.

## Decisions

### D1 — Reuse the rating partials for `range` rather than writing range-specific ones

The two existing partials already produce what is being asked for. Extend the template branch to
cover `range`, and let `display_style` select among slider / `scale_strip` / `list_pips`.

*Why over building a labelled slider:* putting every label under a slider is the obvious-looking fix
and the one that does not survive contact with a 9-point scale on a phone — the labels either
overlap, truncate, or need rotation, and each of those is a new thing to maintain. `list_pips`
sidesteps the geometry entirely by giving each choice a row. Reusing it also means a creator sees
the same three options and the same visual language on `rating` and `range`, instead of two
different vocabularies for the same idea.

*Cost:* `scale_strip` and `list_pips` present radio buttons, which is a different interaction from
dragging a slider. That is the creator's choice to make, which is exactly why this is a per-question
setting and why the slider stays the default.

### D2 — The form field type follows the display style

`scale_strip` and `list_pips` iterate the field's choices (`{% for radio in field %}`), which an
`IntegerField` does not provide. So:

- `default` → `IntegerField` + `RangeWidget` (today's behaviour)
- `scale_strip` / `list_pips` → `ChoiceField` + `RadioSelect`, built from `question.choices`

`_get_form_from_input_type` must therefore receive the resolved display style, which today is
attached to the widget *after* the field is built (`forms.py:251-255`). Resolution moves ahead of
field construction.

*Why this is safe:* both field types post a single value, and the save path keys on `input_type`, so
`float(result[0])` still stores the same number. Verified in tasks by round-tripping an answer
through each style and asserting identical stored values.

*Consequence to handle:* prepopulation on back-navigation sets `initial[code] = int(answer.numeric)`
(`views.py:716-718`). A `ChoiceField` needs the string form to match a choice, so initial resolution
becomes style-dependent too.

### D3 — Express the thumb inset once, in CSS, and let both rows use it

Introduce a custom property for the thumb size on the slider block and derive the tick and label
padding from it, instead of two hand-tuned pixel values that were never equal. The labels then sit
under the extreme positions the thumb can occupy.

*Why not `justify-content: space-between` with corrected padding on each row separately:* that is
the current shape and it drifted. One declared value that both rows consume cannot drift.

### D4 — `default` keeps meaning "slider" for `range`, and inherits nothing

For `rating`, `default` resolves to the survey-wide `rating_display_style`. For `range` it resolves
to the slider. This asymmetry is deliberate: making `range` inherit the rating default would silently
change how every existing range question renders on first deploy, for every creator, without anyone
asking for it. Non-Goals records the survey-wide range default as available later if wanted.

### D5 — Ungate "Display as" by capability, not by a growing list of types

The editor shows the control when `input_type === 'rating'` (`question_form_modal.html:213-216`).
Replace the equality test with membership of a named set of types that support display styles, so
the next type to gain them is a one-line addition rather than another `||`.

## Risks / Trade-offs

**A 9-point `scale_strip` on a narrow phone gives nine cells of a few pixels each** → Real, and it
already applies to `rating` today, so this change does not introduce it. Worth measuring at 320px
during implementation and, if it is as bad as expected, saying so in the editor's style picker
rather than silently letting creators pick it. Recorded as a task, not fixed here.

**Switching style mid-collection changes the respondent's experience between sessions** → No data
consequence, since storage is identical, but a survey that looks like a slider on Monday and buttons
on Tuesday may confuse a returning respondent. The creator's call; the read-only lock on published
surveys already governs when it can happen.

**`ChoiceField` and `IntegerField` differ in what `required` means and in what an empty submit
does** → Covered by tests in both styles rather than reasoned about; a required range question must
behave the same either way.

**The slider fix changes the appearance of every existing range question** → That is the point, and
it is a correction rather than a redesign: the same slider, with the labels where they belong.

## Migration Plan

No schema change and no migration — `display_style` already exists on `Question` with the three
values needed, defaulting to `default`. Nothing is backfilled: every existing `range` question keeps
`default`, which keeps rendering the slider.

Rollback is a revert. No stored data depends on which style was in force.

## Open Questions

- Does a `range` question with no `choices` defined exist in production? The slider falls back to
  0–10 when choices are empty (`forms.py:191-195`), but `scale_strip` and `list_pips` have nothing to
  render. The editor should either prevent selecting those styles or the renderer should fall back to
  the slider; resolving this needs a look at real data, and the safe default in the meantime is to
  fall back.
- Is the "slider is too short" part of the report about the slider or about the width of the question
  card that contains it? It is `width: 100%` of the card, so it needs reproduction at the widths a
  respondent actually sees before anything is changed.
