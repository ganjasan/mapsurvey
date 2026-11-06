# Vision and Scope: Map Styles

**Project:** Mapsurvey — Map Styles (workspace library of custom base-map styles)
**Version:** 0.1
**Date:** 2026-11-06
**Author:** Artem Konuchov
**Status:** Approved by sponsor 2026-11-06

**Revision history:**
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-11-06 | A. Konuchov | First draft, from the 2026-11-06 discussion |

---

## 1. Business Requirements

### 1.1 Background and Strategic Opportunity

Every Mapsurvey survey is a map first. Today the creator picks the base map from a fixed list: Streets, Satellite, Topo and, since PR #511 (2026-11-06), two print-oriented presets, Paper A and Paper B. The list is global, lives in code, and a creator cannot change how any of them looks.

Two things changed this autumn:

- **Paper responses (epic #350)** brought printing into the product. A printed form needs a base map that stays readable in greyscale and on a photocopy; the online Streets map does not. Paper A was built for that, by hand, in the Mapbox account, and the pen-mark reader (#495) is more reliable on it than on Streets (#534, #535).
- **Clients bring their own cartography.** Remington (planning consultancy) ran a survey with a map styled like their own deliverables: white streets, bold labels, pale green parks, turquoise water. Paper B reproduces it, again by hand. Requests for custom base maps keep arriving (#304: official state orthophotos as WMS/XYZ; the GHD and R. M. Towill enquiries in September about GIS linework and base map control).

Each such request today costs a developer session in Mapbox Studio or a script, produces one more hard-coded slug, and helps exactly one client. A planner who wants a map that matches their report cannot get it without us.

### 1.2 Business Opportunity

The customers who care about the look of the map are the ones who pay: planning consultancies, municipal planning departments, engagement agencies. They produce reports, posters and printed forms where the survey map sits next to their own cartography, and the Mapsurvey map is expected to match. The same customers run many surveys a year and want the style set once.

Map Styles turns a one-off service into a **Pro feature**: a workspace-level library where a creator builds a style from guided controls, previews it online and in print, and uses it in any survey. It joins API, MCP and unbranded surveys as a reason to upgrade, and it closes the hand-made-style loop for us: Paper A and Paper B become the first two entries of the library instead of two more settings in code.

### 1.3 Business Objectives and Success Criteria

| ID | Business objective | Success criterion | Deadline |
|----|--------------------|-------------------|----------|
| BO-1 | Make Map Styles a visible Pro driver | Map Styles appears among the three most-used Pro features by workspace count (PostHog) | 6 months after launch |
| BO-2 | Stop hand-made base maps | Zero base-map styles added to code or built in Mapbox Studio for a single client after launch; all client requests served through the library | From launch |
| BO-3 | Styles get reused, not re-made | In workspaces with at least one custom style, ≥ 50% of such styles are used by two or more surveys | 6 months after launch |
| BO-4 | Printed forms read better | Pen-mark recognition false positives per page on a custom print style are not worse than on Paper A (benchmark from #535) | At launch |

*To confirm with the sponsor:* the BO-1 ranking target and the 6-month horizon.

### 1.4 Customer or Market Needs

**Planning consultancies and engagement agencies**
- Want the survey map to look like their own maps: palette, label density, no commercial POI icons, no clutter from neighbouring layers.
- Reuse the same look across all projects for one client; today they re-explain it to us per survey.
- Need an online map and a printed map that are recognisably the same style while each works in its medium.

**Municipal planners**
- Need a calm map under their own reference layers (proposals, boundaries): fewer labels, muted colours, so the proposal reads first.
- Need print-ready maps for workshops and paper forms without a GIS specialist.

**Mapsurvey (ourselves)**
- Keep Paper A and Paper B, and any future preset, as data rather than code and Mapbox-account state.
- A format for a style that can be exported, imported into another workspace, and later published in a shared catalogue.

**What they cannot do today**
- Change anything about a base map. Base maps are five fixed slugs.
- Share a map look between surveys or between workspaces.
- See how a map will print before printing it.

### 1.5 Business Risks

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| BR-1 | Rendering architecture. Respondent and editor maps run on Leaflet with raster tiles. A per-workspace style needs either a vector renderer (MapLibre / Mapbox GL) on every map surface or one hosted Mapbox style per custom style. Mapbox limits styles per account and bills tile and static requests per style. | H | H | Decide the rendering path in a dedicated investigation before the editor is built (see DE-1). Prototype both paths on the respondent map with Paper A. |
| BR-2 | Scope creep into a map-design tool. Users ask for layer-level control, custom fonts, sprites, their own data as base map. | H | M | Guided controls only (FE-3); layer-level editing, fonts and sprites are explicit exclusions (3.3). Custom tile sources stay in #304. |
| BR-3 | Illegible user-made styles. A creator picks colours that fail on print or for respondents with low vision; survey layers become invisible on the base. | M | M | Controls are bounded (palettes, density steps), not free colour pickers. Print preview is greyscale. Contrast warnings in the editor. |
| BR-4 | Base style drift. Styles derive from a Mapbox base (`streets-v12`); when Mapbox retires it, every derived style must be rebuilt. | M | M | Store the creator's settings, not the generated style; regenerate from settings on base upgrade. Pin the base version per style. |
| BR-5 | Mapbox cost. Each custom style multiplies tile cache misses; static previews in the editor are billable. | M | M | 512 px tiles (#522), throttled previews, cost per style tracked in PostHog. |
| BR-6 | Changing a style silently changes live surveys. A creator edits a style used by a published survey and respondents see the change mid-collection. | M | M | Editor shows "used in N surveys" and warns before saving; a survey version pins the style version. |

---

## 2. Vision of the Solution

### 2.1 Vision Statement

**FOR** planning consultancies, municipal planners and engagement agencies on Mapsurvey Pro
**WHO** need the survey map, online and on paper, to look like their own cartography and to stay consistent across all their surveys
**THE** Map Styles library **IS A** workspace-level collection of base-map styles
**THAT** lets a creator build a style from a handful of guided controls, see it as respondents and as print will see it, and use it in any survey with one click
**UNLIKE** editing in Mapbox Studio, exporting from QGIS or asking the vendor for a custom base map
**OUR PRODUCT** needs no GIS skills, keeps online and print views of one style in step, and makes a style a portable object: duplicated, exported, imported, and later shared in a catalogue.

### 2.2 Major Features

| ID | Feature | Description | Related BO |
|----|---------|-------------|------------|
| FE-1 | Style library | A "Map styles" page in the workspace sidebar: cards with a preview, name, base preset, number of surveys using it; duplicate, export, delete. | BO-1, BO-3 |
| FE-2 | System presets | Streets, Satellite, Topo, Paper A, Paper B live in the same library as read-only entries that any workspace can duplicate as a starting point. Paper A and Paper B stop being code. | BO-2 |
| FE-3 | Guided style editor | A bounded set of controls: POI icons, buildings, label density, place-name level, park and water palette, road contrast, greyscale mode. No layer-level editing. | BO-1, BO-2 |
| FE-4 | Online and print preview | Side-by-side previews on the frame of any of the workspace's surveys: the respondent map and a greyscale print sheet. | BO-4 |
| FE-5 | Use in any survey | Workspace styles appear next to system presets in survey Base maps and section overrides; existing surveys keep working unchanged. | BO-3 |
| FE-6 | Import and export | One JSON file per style: schema version, base preset, settings. Exported from one workspace, imported into another, independent of any Mapbox account. | BO-3 |
| FE-7 | Usage and change safety | "Used in N surveys" on every style; warning before saving a style in use; a survey version keeps the style version it was published with. | BO-3 |
| FE-8 | Pro gating | Browsing and using system presets is free. Creating, editing, duplicating, importing and exporting styles requires the `map_styles` Pro feature, checked on the owning workspace like `api`. | BO-1 |
| FE-9 | Shared catalogue | Publish a style for other workspaces to browse and copy; curated and community entries. | BO-1 |
| FE-10 | Styles via API and MCP | List, export and attach styles through API v2 and MCP, so an agent can set up a client's workspace. | BO-3 |

### 2.3 Assumptions and Dependencies

**Assumptions**
- AS-1: Creators are satisfied by 6–8 guided controls over a Mapbox base; nobody needs per-layer editing to match their house style at survey scale.
- AS-2: A style is derived from one Mapbox base style (`streets-v12` today) and the system can regenerate it from stored settings.
- AS-3: Satellite stays a fixed provider (Esri) and is not styleable; a custom style may only pick whether satellite remains available alongside it.
- AS-4: Respondents do not need to switch between custom styles; the existing layer switcher stays as it is.

**Dependencies**
- DE-1: **Rendering path decision.** Either the map surfaces move to vector tiles (MapLibre or Mapbox GL via a Leaflet bridge) and render the style JSON directly, or every custom style is uploaded to the Mapsurvey Mapbox account and served as raster through the Styles API. This decision gates FE-3 to FE-5 and must be made first.
- DE-2: Mapbox Styles API and Static Images API availability, quotas and pricing.
- DE-3: `billing.features` registry and `billing.entitlements` for the Pro gate (spec `api-pro-gate`).
- DE-4: The print pipeline from epic #350 (`printable-form`, `paper-photo-entry` specs) consumes the style for the form and for the recognition reference image.
- DE-5: Epic #350 follow-ups #534 (print base map) and #535 (mark recognition research) define the print legibility benchmark (BO-4).

---

## 3. Scope and Limitations

### 3.1 Scope of Initial Release (v1.0)

- FE-1 Style library — the home of the feature, the sidebar entry.
- FE-2 System presets — Paper A and Paper B migrate from settings into library data; this is the first consumer of the style model.
- FE-3 Guided style editor — the core value.
- FE-4 Online and print preview — a style without a print preview does not serve the paper use case that started this.
- FE-5 Use in any survey — otherwise the library is decoration.
- FE-6 Import and export — part of the sponsor's definition of the module and the basis of the future catalogue; cheap once the style is a JSON document.
- FE-7 Usage and change safety — needed as soon as one style serves two surveys.
- FE-8 Pro gating — ships with the feature, not after.

Preceded by the rendering investigation (DE-1), which is its own issue and may change the shape of FE-3 to FE-5.

**Target release:** to be set after DE-1 is resolved.

### 3.2 Scope of Subsequent Releases

**v1.1**
- FE-10 Styles via API and MCP — once API v2 layers work (#411) is stable; the export format from FE-6 is the payload.

**v2.0**
- FE-9 Shared catalogue — needs moderation, licensing of style names and a discovery UI; wait for a few dozen real styles to exist.
- Style-aware recommendations in AI survey generation (pick a preset by survey type).

**Later / separate**
- Custom tile sources as a base for a style (WMS, XYZ, orthophotos) — tracked in #304, orthogonal to styling.

### 3.3 Limitations and Exclusions

The following is **not** in scope:

1. A general map-design tool: no per-layer editing, no custom fonts or sprites, no uploading of arbitrary Mapbox style JSON. A style is a set of bounded settings over a Mapsurvey base.
2. Styling of satellite imagery, or any non-Mapbox provider.
3. Styling of survey layers (reference layers, place types, respondent marks). That remains the existing layer styling.
4. Per-survey editing of a style. A survey picks a style; it does not fork it. Duplicate in the library instead.
5. Respondent-side style choice beyond today's base-map switcher.
6. Custom tile sources (WMS/XYZ, #304) and client-hosted Mapbox accounts.
7. Branding of the Mapsurvey app itself (logo, colours of the UI); that is a separate "unbranded" feature.
8. The shared catalogue (FE-9) in v1.0.

---

## 4. Business Context

### 4.1 Stakeholder Profiles

| Stakeholder | Role | Main interests | Influence |
|-------------|------|----------------|-----------|
| Artem Konuchov | Sponsor, product owner, sole developer | Pro conversion; no more hand-made styles; feature stays small enough for one developer | High |
| Pro creators (planning consultancies, agencies — e.g. Remington, Gensler, Unknown Studio) | Primary users | Map matches their cartography; one style for all surveys; print-ready | High |
| Municipal planners | Primary users | Calm base under proposals; print for workshops; no GIS needed | Medium |
| Free creators | Users | System presets stay available; upgrade path is clear, not a wall | Low |
| Respondents | Indirect users | Legible map on phone and paper; nothing new to learn | Medium (via legibility) |
| Paper-form operators (reading photographed forms) | Users | Base map that the mark reader handles well | Medium |
| Mapbox | Vendor | Account limits, pricing, base-style lifecycle | Medium |

### 4.2 Project Priorities

| Dimension | Constrain | Optimize | Accept |
|-----------|:---------:|:--------:|:------:|
| Schedule | | | ✓ |
| Features | | | ✓ |
| Quality | | ✓ | |
| Cost | ✓ | | |
| Staff | ✓ | | |

- **Staff** is fixed: one developer with Claude Code.
- **Cost** is constrained: the Mapbox bill must not grow faster than Pro revenue; no new paid services.
- **Quality** is optimised: a style must look right online and in print, and must not break mark recognition.
- **Schedule** and **Features** flex: ship the library with fewer controls rather than later with more.

### 4.3 Deployment Considerations

**Target environment:** the existing Django application on Render (web + Celery worker), Mapbox account owned by Mapsurvey. Depending on DE-1, either a vector-tile client library is added to the map surfaces or the worker gains a job that publishes styles to Mapbox.

**Data migration:** `basemaps`, `default_basemap` and `override_basemap` on surveys and sections hold fixed slugs today. They become references into the style library; existing slugs map to the system presets so no survey changes behaviour. Paper A and Paper B move from environment settings into library rows.

**Training and transition:** a Help Centre page ("Map styles") and a "What's new" card; system presets need no explanation. Pro upsell copy on the library page for Free workspaces.

---

## 5. Appendix

### 5.1 Glossary

| Term | Definition |
|------|------------|
| Base map | The background map under survey layers, served as tiles. |
| Style | A named set of settings over a base preset, owned by a workspace, that produces a base map look online and in print. |
| System preset | A read-only style shipped by Mapsurvey (Streets, Satellite, Topo, Paper A, Paper B). |
| Workspace | The organisation that owns surveys and styles (`Organization` in code). |
| Pro | The paid plan; features gated through `billing.features`. |
| Print preview | A greyscale rendering of the style at form scale, matching what the printable form will produce. |

### 5.2 Related documents

| Document | Location |
|----------|----------|
| Epic: Map styles | ganjasan/mapsurvey #545 (issues #541–#544) |
| Epic: paper responses | ganjasan/mapsurvey #350 |
| Printed form base map | ganjasan/mapsurvey #534 |
| Mark recognition research | ganjasan/mapsurvey #535 |
| Custom basemap WMS/XYZ | ganjasan/mapsurvey #304 |
| 512 px raster tiles | ganjasan/mapsurvey #522 |
| Spec: basemap-providers | `openspec/specs/basemap-providers/spec.md` |
| Spec: api-pro-gate | `openspec/specs/api-pro-gate/spec.md` |
| Spec: printable-form, paper-photo-entry | `openspec/specs/…/spec.md` |
| Paper A / Paper B implementation | PR #511 |

---

*Prepared following Wiegers, K., Beatty, J. "Software Requirements, 3rd Edition". Microsoft Press, 2013.*
