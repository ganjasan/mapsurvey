## Context

Today `SurveySection.layout` is a binary: `map` (panel `#info_page` absolutely positioned at
the left, 420 px, the map under everything; `.leaflet-top.leaflet-left` and `#showButton`
offset from it in `main.css`) or `form` (`body.survey-form-layout`: the map and every piece of
map chrome `display:none`, the panel becomes a centred card). The mode is set server-side on
`<body>` for a direct load and toggled client-side from `#section-data[data-layout]` in the
HTMX section-swap step of `base_survey_template.html` (step "0. Layout mode"), because the
map instance must survive navigation. Below 768 px the panel is an 88 % overlay from the left
edge and the Leaflet corner has no offset.

Three new per-section controls must land on top of that without changing a single existing
survey's rendering (issue #473).

## Goals / Non-Goals

**Goals**
- Three independent settings on the section: stage (`layout`: `map | form | image`), `panel_side`
  (`left | right`), `panel_width` (`default | third | half`); a section picture for the image stage.
- Defaults reproduce today's output byte for byte; `form` ignores side and width.
- One switch per concern in CSS so the mobile block, the embed and future presets stay simple.
- The settings are content edits on a live survey and travel everywhere a section travels.

**Non-Goals**
- Partner logos, muted basemap, image choices, theme presets, custom domain (later steps).
- A free-form width, drag-to-resize, or per-question layout.
- Uploading the section picture through the REST API / MCP (`stage_image` is read-only there
  in this change; the ZIP import and the editor are the two upload paths).
- A bottom-sheet or any other change to the respondent's mobile map flow (owner decision
  2026-08-23 stands).

## Decisions

### D1. Extend `layout`, add two plain columns and one image column
`layout` keeps its name and gains `image` (`SECTION_LAYOUT_CHOICES`). New
`panel_side = CharField(5, choices, default='left')`, `panel_width = CharField(8, choices,
default='default')`, `stage_image = ImageField(upload_to='sections/', null, blank)`. Choice
constants and the map-less set live in `survey/models.py`:
`MAPLESS_LAYOUTS = ('form', 'image')`. `SurveySectionForm.clean_layout`, the geo check in
`QuestionForm`, the type-picker filtering and the import cleaner all read that constant —
one definition, as the geo-exclusion requirement demands.

*Why not a JSON "style" blob:* three enumerations and a file; plain columns are what
`plain_field_values`, the forms bridge and the ninja schemas already handle, and a JSON blob
would need its own validator on every write path.

### D2. Rendering = body classes + one CSS variable
Server and client set the same classes on `<body>`:
- `survey-form-layout` (existing) for `form`; `survey-image-layout` for `image`; both share the
  "no map chrome" rule block (`body.survey-form-layout, body.survey-image-layout { … }`).
- `panel-right` for `panel_side = right` on `map`/`image` only.
- `panel-w-third` / `panel-w-half`; the default sets nothing.

Width is ONE custom property: `:root { --panel-w: 420px }`, `body.panel-w-third { --panel-w:
33.333vw }`, `body.panel-w-half { --panel-w: 50vw }`. `#info_page { width: var(--panel-w) }`
(and `max-width: none` under a preset class), `.leaflet-top.leaflet-left { left: calc(var(--panel-w)
+ 16px) }` — today's literal `436px` becomes `420 + 16`, so the default is unchanged.

Side is a mirror block: under `body.panel-right`, `#info_page { left:auto; right:0; border-left …;
border-right:0 }`, `#info_page.hidden { transform: translateX(100%) }`, `#showButton { left:auto;
right:12px }`, `.leaflet-top.leaflet-left { left: 10px }` and the symmetric offset on
`.leaflet-top.leaflet-right`, the `#closeButton`/`#showButton` chevrons flipped. The draw bar is
centred (`left:50%`) and needs nothing. Anything else absolutely positioned over the map that
offsets from the panel is found by grepping `436px`/`#info_page` in `main.css` during
implementation and gets its mirror rule in the same block.

Client side, the HTMX step generalises `isFormLayout` into `applyLayout(dataEl.dataset)`:
toggles the five classes from `data-layout`, `data-panel-side`, `data-panel-width`, sets the
stage picture, and calls `map.invalidateSize()` only when the new stage is `map` (the existing
`_pendingMapTarget` logic unchanged). Geolocation keeps its `form` guard but on
`layout !== 'map'`.

### D3. The picture is an element beside `#map`, fed from the section data
`<div id="stage-image">` sits next to `<div id="map">` in `base_survey_template.html`
(outside the swapped panel), `position:absolute; inset:0; background-size:cover;
background-position:center; display:none`, shown under `survey-image-layout`. Its URL comes
from `#section-data[data-stage-image]` = `section.stage_image.url` or
`survey.cover_image.url` or `""`; the server writes the same `style="background-image:url(…)"`
for a direct load. With an empty URL the element stays a tinted area (`background:
var(--accent, var(--panel-bg))`) — no `<img>`, so no broken-image icon. A background, not an
`<img>`, because the stage must cover whatever viewport the host gives, including an embed.

The panel cannot be hidden on an image stage: `#showButton`/`#closeButton` are in the hidden
chrome set for both map-less layouts.

### D4. Mobile: side and width are desktop-only; image = band + column
The existing `@media (max-width: 768px)` block already resets `#info_page` to the 88 % overlay
with `left:0` and the Leaflet corner to `left:0`. The desktop mirror and width rules are
written OUTSIDE that block and the mobile block re-asserts `left:0; right:auto; width:88%;
transform` for `#info_page` and `#info_page.hidden { translateX(-100%) }` regardless of the
side classes, so a phone never sees them (cascade order, no JS branching on viewport).

For `survey-image-layout` on mobile: `#stage-image { position:relative; height:38vh }`,
`#info_page { position:relative; width:100%; max-width:none; height:auto; transform:none }`,
`body { overflow:auto }` — the page becomes one scrolling column, picture first. The embed
height report (`survey-form-layout` guard) stays form-only: an image section fills the host's
viewport like a map section, on every width.

### D5. Editor: multipart section form, a Layout block, one show/hide script
`SurveySectionForm.Meta.fields` += `panel_side`, `panel_width`, `stage_image`
(`ClearableFileInput`); `editor_section_detail` passes `request.FILES` and
`services.sections.update(actor, section, data, files=None, …)` forwards them to `bind`.
`section_detail_form.html` gets `enctype="multipart/form-data"` + `hx-encoding` (HTMX sends
FormData for a multipart form) and renders the four fields in a "Layout" `<fieldset>` after
the base fields; the existing inline script that disables the Map position button on `form`
grows into `syncLayoutControls()` keyed on `#id_section_layout`: side+width visible for
`map|image`, picture for `image`, Map position enabled for `map`. Labels/help texts in the
form's `labels`/`help_texts` dicts; new strings appended by hand to every offered catalog.

The Preview pane needs nothing: `editor_section_preview` renders the real respondent page.

### D6. Copies, ZIP, API
- Draft copy / duplicate / paste: `plain_field_values` carries the three plain fields and the
  image NAME; `copy_section` copies the file to a new key when the target is another survey
  family, exactly the `Question.image` branch in `clone_question` (`same_family`). Purge of a
  trashed survey deletes `stage_image` files alongside covers and question images.
- ZIP: `serialize_sections` adds `panel_side`, `panel_width`, `stage_image` (name); the picture
  is written as `images/sections/<section code>_<basename>` next to `images/structure/`, and
  import extracts it by section code the way question images are (a mismatch is a warning
  line, not a failure). Import whitelists the three values against the model choices and
  falls back to the default.
- REST: `SectionIn.layout: Literal['map','form','image']`, `panel_side`, `panel_width` as
  `Literal`s; `SectionOut` adds the three plus `stage_image: Optional[str]` (absolute URL,
  read-only). `forms_bridge.SECTION_FIELDS` += the two names. MCP `create_section` /
  `update_section` descriptions name the values; both references regenerated.

### D7. Safe edit
`structural_section_changes` does not look at these fields, so the live-survey path treats
them as content — no code change, one test that proves it.

## Risks / Trade-offs

- **Hidden map chrome that offsets from the panel** (search box, basemap switcher, layers
  button): a missed element renders under the panel on `panel-right`. Mitigation: grep for
  every `436px`/`#info_page`-relative rule and add it to the mirror block; a manual pass on
  the respondent page at desktop width with each side × width × stage before the PR.
- **`vw` presets inside an embed**: `33vw` of the host's iframe, which is what the creator
  expects; the min width of the panel is kept at 320 px so a narrow iframe does not crush
  the column.
- **Multipart section form**: the section modal was urlencoded; HTMX switches to FormData with
  `hx-encoding`. Verified by the editor test that uploads a picture through the modal.
- **Large pictures**: `stage_image` is a plain `ImageField` like `cover_image` — same size
  limits, same public tier; no new memory path (it is never read into a worker).

## Migration Plan

One migration (`0106`): add `panel_side`, `panel_width` with defaults, `stage_image` nullable,
widen `layout` choices (no column change). Backwards compatible; nothing to backfill; rollback
is reverting the migration.

## Open Questions

- Whether the Structure list should badge a section with a non-default layout (a small
  "Image · right · half" caption under the row). Deferred until the controls are used.
