# The map follows the answer — show only the respondent's own area

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-08-23

## Description

An earlier answer scopes the map for everything that follows. The respondent picks their
assigned area from a dropdown; the map then zooms to that area's geometry, draws only that
overlay feature, and (optionally) refuses geometry placed outside it.

This is branching, but for the map rather than for the question list: the condition comes
from a previous answer exactly as in [conditional question
visibility](feature-conditional-question-visibility.md) (#12), while the thing being
switched is map context — extent, visible overlay features, allowed drawing bounds.

Live case: Olney's 35 counting areas ([[lead-olney-squirrel-count]]). A volunteer assigned
Area 13 currently sees the whole town and must find their zone themselves; the paper map
they are replacing shows one zone and nothing else. Showing all 35 outlines at once is
worse than showing none — it is the same wall-of-options problem the 35 radio buttons had.

Second live case, 2026-08-27: BC3 (Basque Centre for Climate Change) asked for exactly
this unprompted — a felt-heat survey across three Bilbao neighbourhoods, where picking
your neighbourhood recentres the map on it. Two independent asks, from a field-count
volunteer flow and from an urban research flow, converging on the same gesture. Note the
difference in scale: three areas, not 35, which is why the workaround below is tolerable
there and is not for Olney.

## What it needs

- Overlay layers with per-feature identity (#136) — the zone polygons must be addressable,
  so the uploaded GeoJSON needs a key field mapped to the choice codes.
- A rule on the geo question: "scope to the feature selected in question X".
- **Both directions, decided 2026-08-25.** The item was written as answer -> map only,
  but the reverse is the more natural gesture for the volunteer this is for: tapping
  your zone on the map is easier than finding "Area 13" in a list of 35. So the change
  covers map -> answer too (click a zone, the choice question fills in). FD-1 ships the
  layer with `interactive: false` precisely so tap-to-place is never swallowed; making
  zones clickable has to keep that guarantee — a zone click may only select while the
  respondent is NOT in geometry-placement mode.
- `key_field` already exists on the layer (shipped with FD-1) and serves both directions;
  what is missing is the editor UI binding it to a choice question's codes.
- A decision about enforcement: soft (zoom + highlight, placement anywhere still allowed)
  vs hard (a point outside the zone is rejected). Soft first — a volunteer standing one
  street over the boundary must not be blocked from recording a real observation, and
  `validation_settings` already exists for the strict variant later.

## Notes

- **Today's workaround, and where it runs out.** One section per area, each with its own
  `start_map_postion`/`start_map_zoom`, each gated by a `visibility_rule` on the area
  question: the respondent sees only their section and the map flies there on entry. This
  is what BC3 was told on 2026-08-27. It covers the recentring half only — no per-feature
  highlight, no drawing bounds, no map -> answer direction — and it costs one hand-built
  section per area, so it stops being viable somewhere between three areas and 35. The
  flyTo also fires on section entry rather than on the click, which is the visible seam.
- Also solves the assignment problem without per-person links: the volunteer self-selects
  their zone and the map reshapes. Volunteer links (#137) make it automatic rather than
  self-declared, but this works without them.
- Generalises well beyond counts: pick your district → draw inside your district; pick a
  school → map centres on its catchment.
- Sequencing: #136 → this → optionally #137. All three are what Olney actually asked for
  under the name "assign counting areas to volunteers".
- Epic: field-data-collection (FD-14)
