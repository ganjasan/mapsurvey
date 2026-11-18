## 1. Shell and survey editor on the tokens

- [x] 1.1 `scripts/tokenise_colours.py`: colour + where it stands (text / line / surface) → purpose token; leaves `<script>` alone; lists what it does not know
- [x] 1.2 Inverse, veil, rating tokens in `tokens.css`; older names moved there
- [x] 1.3 Shell, dashboard, survey editor, dialogs, settings panel; hand-fix the rest
- [x] 1.4 Browser check (sign-in, dashboard, Build, question dialog, settings)

## 2. Every other creator module (owner: one PR)

- [x] 2.1 Extend the table (slate, Tailwind blues, translucent indigo, dark shadows); run over every creator file that renders under the tokens
- [x] 2.2 Hand-fix: module palettes → token references; backdrops, glass, dark viewer, identity colours, illustrations into `tokens.css`
- [x] 2.3 Test: every creator file outside the listed exceptions holds no declared colour; baseline lowered
- [x] 2.4 Browser check of every module; full suite; CLAUDE.md
