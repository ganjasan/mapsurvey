# Proposal: fix-story-callout-dark-mode

## Why

On a device in the dark colour scheme the **Lessons learned** callout of a customer story
(`<aside class="sd-lessons">`) is unreadable: the block paints a hard-coded light surface
(`#FBF3EC`, `#fff` for the "In Mapsurvey" lines) while its paragraphs and headings inherit the
theme's body text, which the dark theme turns to `#E0E6F0` — light text on a light card. Reported on
a phone, but any dark-mode viewport shows it. The staff-only draft banner (`.sd-draft-banner`) has
the same hard-coded light surface. The callout also read `--text-primary` / `--text-secondary`,
tokens `landing.css` never defines, so it always fell back to the light values.

## What Changes

- `.sd-lessons` sets its own text colour and keeps every colour in local `--ll-*` tokens.
- One `prefers-color-scheme: dark` rule redefines those tokens. The block must still stand out the
  way the beige card does in light mode: a warm surface lighter than the page (`#33231A` on
  `#0D1117`), an accent outline, "In Mapsurvey" lines sunk into the card instead of separate cards;
  contrast ≥ 4.5:1 for every text pair (lowest 7.1:1).
- `.sd-draft-banner` gets a dark variant.
- Light theme is unchanged pixel for pixel in intent (same colour values).

## Impact

- `survey/assets/css/landing.css` only. No template, model or story body changes.
