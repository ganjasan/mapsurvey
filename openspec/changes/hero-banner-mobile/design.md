## Context

`_whats_new_hero.html` is a three-column grid (plate · text · actions) that collapses to one
column under 760 px. The dashboard's own breakpoints are 768 px (`editor.html`), and the
mobile editor chrome uses 767.98 px.

## Decisions

**One markup, CSS decides.** The partial gains a `<button class="wn-hero-toggle">` row (badge,
title, chevron) rendered on every viewport and hidden on desktop. Under 767.98 px the plate,
text and actions are hidden unless the section carries `wn-hero-open`. No second template and
no server-side user-agent sniffing: the same response serves both widths, so the existing
tests and the watermark logic need no branch.

**Collapsed is the default on phones, every visit.** The state is not remembered: a creator who
expanded it once and left it will see it closed again on the next dashboard load. That is the
point — the dashboard is for surveys. The × closes it for good, as before.

**The toggle carries `aria-expanded` and `aria-controls`** pointing at the body wrapper, so a
screen reader announces it as a disclosure.

**Breakpoint 767.98 px**, the mobile editor's, replacing the hero's own 760 px so a 761–767 px
window does not get a half-mobile layout.

**Event `changelog_card_expanded`** (`entry_id`, `tier: 'hero'`), fired on the first expand per
page only. Ids only, like the other changelog events.

## Risks

- A phone creator who never taps sees only the title. Accepted: the title is written to sell on
  its own, and `changelog_card_expanded` will show whether phone creators open it.
