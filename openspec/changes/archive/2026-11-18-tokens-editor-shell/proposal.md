## Why

Change `design-tokens` (#740) gave the creator app one file of tokens, but the pages still wrote
their own colours: 1706 literals in 72 files, with the same role in a different shade from block to
block (three greys of body text, four reds, five greens, Bootstrap blue and teal next to indigo, a
second palette per module). The owner asked for one consistent design across the app (#742): first
module by module, oldest and most used first, then all of it in one PR.

## What Changes

- Every creator template and stylesheet that renders under `css/tokens.css` takes its colours from
  purpose tokens: the shell, dashboard, survey editor, Responses, comments, Share, create and start
  pages, translations, Sites and report builders, Data, paper entry, map styles, billing, API
  connections, What's new. Shadows become `--shadow-sm|md|lg`, focus rings `--focus-ring`.
- One shade per role: a colour is chosen by what it is for, so near-duplicates collapse onto the
  token. Module palettes (`--app-side-*`, `--pro-*`, `--tb-*`, `--tt-*`) are references to tokens.
- New tokens: `--surface-inverse` (+ `-deep`, `-raised`, `--color-border-inverse`),
  `--color-on-inverse(-muted)`, `--surface-veil`, `--surface-glass`, `--backdrop(-strong)`,
  `--shadow-on-map`, `--color-rating`; identity colours `--type-*` and `--heat-ramp`; pictures
  `--brand-mark`, `--brand-claude`, `--art-*` — they keep their colours, but in the one file.
- The sign-in pages lose their beige and teal; the agent banner's orange button becomes the action
  button. The older names (`--accent`, `--border-color`, …) move into `tokens.css`.
- A test fails when any creator file writes a colour in a CSS declaration outside `<script>`; the
  five files that render without the tokens (two emails, an iframe preview, the public site page,
  the plan cards also drawn on the pricing page) are listed with the reason.
- Not moved: colours inside `<script>` (map palettes, colour inputs, iframe `srcdoc`), the
  `theme-color` meta tag.

## Capabilities

### Modified Capabilities
- `design-tokens`: creator files hold no colour literals.

## Impact

64 templates and stylesheets, `survey/assets/css/tokens.css`, `survey/tests/test_design_tokens.py`,
`survey/tests/colour_baseline.json` (1706 → 163, the rest in scripts and the five exceptions),
`scripts/tokenise_colours.py` (new). Small visible shifts: labels one shade darker, some reds and
greens one shade off, Bootstrap-blue and teal accents become indigo, shadows unified.
