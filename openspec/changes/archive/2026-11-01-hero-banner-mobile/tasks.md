## 1. Markup and behaviour

- [x] 1.1 `_whats_new_hero.html`: a toggle row (badge, title, chevron) with `aria-expanded` /
      `aria-controls`; plate, text and actions wrapped in one `wn-hero-main` element
- [x] 1.2 JS: the toggle flips `wn-hero-open` and `aria-expanded`; first expand captures
      `changelog_card_expanded`; no watermark POST

## 2. Styles

- [x] 2.1 `whats-new.css`: toggle hidden on desktop; below 767.98 px the main block is hidden
      unless open, the × sits on the row, breakpoint 760 px replaced

## 3. Tests and check

- [x] 3.1 `test_changelog_hero_banner.py`: the toggle markup with `aria-expanded="false"` and a
      matching `aria-controls` target
- [x] 3.2 Run `survey.tests.test_changelog_hero_banner` and the changelog tests
- [x] 3.3 Screenshot the dashboard at 390 px collapsed and expanded, and at desktop width
