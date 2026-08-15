# Design — star display style for rating questions

## Context

Rating already resolves a display style per question (`Question.display_style`) with a
survey-wide fallback, and renders through one of two partials chosen by the `uses_scale_style` /
`rating_display_style` template filters. Adding a third style is an entry in three constant
lists, one partial, one CSS block, and one editor thumbnail — the machinery from
`rating-question-display-style` and `range-scale-display` was built for exactly this.

The configurable part is where the design decisions are.

## Decisions

### D1 — Reuse `Question.color` and `Question.icon_class` instead of new fields

Stars need an icon and a colour. Both already exist on `Question`, both already have pickers in
the question dialog (the Font Awesome grid and the colour input), and both were just scoped to
the types that consume them by `question-type-picker`. Extending that scope to "geo types, plus
rating when the style is stars" keeps one rule, one pair of fields, and needs **no migration**.

Rejected: a `display_settings` JSON blob mirroring `validation_settings`. It would duplicate two
fields that already exist, and would need its own editor UI where the pickers are already built.

The cost is that `color` means "marker colour" on a geo question and "star colour" on a rating —
acceptable: it is the question's colour either way, and no question is both.

### D2 — Defaults live in a resolver, not in the database

`Question.color` defaults to `#000000` and `icon_class` to empty. Black stars are not what
"default" should mean, and back-filling gold onto every existing rating question would be a
migration that changes questions nobody asked to change.

So a model helper resolves at render time: icon → `icon_class` or `fas fa-star`; colour →
`color`, treating the model default `#000000` as "never set" and yielding gold `#f5b301`. A
creator who genuinely wants black stars can pick `#000001`, which is the kind of edge case worth
accepting to avoid a migration; it is noted in the spec rather than hidden.

### D3 — The star count is the choice list, with an editor convenience on top

Stars render one icon per choice, exactly as `scale_strip` does. This keeps storage, export and
analytics identical to every other rating question, and means switching styles never reshapes
data.

Making a creator hand-type five choice rows to get five stars is the kind of friction this whole
picker effort exists to remove, so the editor grows a "Number of stars" spinner shown only for
the stars style. It rewrites the choice rows to `1..N`, preserving any names already typed. It is
a convenience over the existing choices editor, not a second source of truth — the choices rows
stay visible and authoritative.

### D4 — Radios underneath, painting on top

The partial renders real radio inputs (one per choice) with the icons as labels, in a
`direction: rtl` flex row so a CSS sibling selector can fill every star up to the checked one
without JavaScript. Hover preview uses `:hover ~` in the same way. Keyboard and screen readers
get an ordinary radio group; `aria-label` carries the choice name.

Rejected: JS-driven fill. The strip and list styles are CSS-only and this must degrade the same
way when JS fails.

### D5 — Survey-wide default includes stars

`get_default_rating_display_style` accepts the new value and the survey settings form offers it.
A survey-wide star default uses each question's own icon/colour resolution, so it stays
consistent with per-question configuration.

## Risks / Trade-offs

- **Long scales look wrong as stars.** Nine stars is not a star rating. The editor hints at this
  the way the strip does for long scales (a note when the count is above ~10), rather than
  forbidding it.
- **Colour contrast**: an unfilled star is an outline in a muted grey; a creator can pick a
  colour that vanishes against white. Out of scope to police, same as marker colours today.
- **`#000000` as a sentinel** (D2) — documented, and the only alternative was a migration.

## Migration Plan

None. New style value, resolved defaults, no schema change. Existing rating questions are
untouched until a creator picks stars.
