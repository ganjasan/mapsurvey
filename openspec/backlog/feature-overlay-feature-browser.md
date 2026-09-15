# Browse the creator's map objects — list, search, filter, click to zoom

**Type**: feature
**Priority**: high
**Updated**: 2026-08-31 — very high → high; useful, but no lead has asked for browsing as such — `#152` is the buyer ask
**Area**: frontend
**Created**: 2026-08-26

## Description

Reference overlay layers (FD-1) put the creator's objects on the respondent's map, but the
respondent can only look at them. This item makes them browsable: a panel beside the map
listing every feature in the layer, with a search box and category chips, wired to the map
in both directions. Click a row — the map flies to that feature, highlights it, and the row
expands into a card with an image, prose and an outbound link. Click the feature on the map
— the same card opens in the list.

This is the single screen the owner singled out after walking PARTIMAP's demo:
["Show it on the map"](../../docs/marketing/competitors/partimap/03-show-it-on-the-map.jpg),
and [the card after a click](../../docs/marketing/competitors/partimap/04-feature-card-zoom.jpg).
It turns a survey into a presentation of the project being consulted on, which is the format
municipal engagement actually arrives in — you explain the plan first, then ask about it.

## What it needs

- Per-feature content on the overlay layer: title, image, rich text, link. Today a layer is
  styled as a whole with one colour and an optional label field; this needs the feature's own
  properties to carry displayable content, and the editor to map GeoJSON properties onto those
  slots (`key_field` already exists from FD-1 and gives features identity).
- A category field mapped to the filter chips, derived from a property.
- Client-side search over the title (and probably the body) — no server round trip; a layer is
  already fully loaded.
- The list ↔ map binding must not swallow taps while the respondent is placing geometry —
  the same guarantee FD-1 bought with `interactive: false`, and the same constraint
  [FD-14](feature-answer-driven-map-context.md) has to respect.
- Rich text through `coerce_creator_html` like every other creator-authored field; a feature
  card is one more way to write markup that reaches every respondent.
- Mobile: the list and the map cannot sit side by side below 768px. The respondent flow was
  deliberately left on the legacy panel/crosshair layout (see CLAUDE.md) — this needs an
  approved mockup before it ships, not an improvised sheet.

## Notes

- Prerequisite for [#152](feature-questions-on-overlay-features.md): asking about a feature
  is only usable once the respondent can find that feature. Build this first, then hang
  questions off the same rows.
- Guards against the wall-of-options problem: 35 zones or 50 assets on a map are unreadable
  without a list, which is the same argument [FD-14](feature-answer-driven-map-context.md)
  makes about 35 radio buttons.
- Also the natural home for [photo in observation popup](feature-photo-in-observation-popup.md)
  (FD-4) on the creator's side of the map.
- Epic: community-engagement
