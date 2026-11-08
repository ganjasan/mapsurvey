## Context

Blocks already render through `landings/blocks/<kind>.html` on the public page from a
`(block, card)` pair built by `landings.page_blocks`; the builder posts plain forms read by
`landing_views._raw_block` and validated by `landings.clean_block`. Nothing in the data layer
changes; the work is the editing surface and the write protocol.

## Decisions

### D1. One rendering, two shells
The canvas includes the public block template for every block (survey cards with their
resolved `card`, results with their payload, events with their form rendered disabled) inside
an editor shell `landings/editor/_canvas_block.html` that adds the kind tag, the hover
toolbar, `data-block` / `data-kind`, and marks text fields editable: `h2[data-field=title]`,
and per kind `body` (text), `caption` / `alt` (image, video, map), `description` /
`button_label` (survey card), `description` / `place` (event), `q` / `a` (FAQ items),
`title` / `when` / `body` (timeline phases), file titles (documents). Plain fields are
`contenteditable="plaintext-only"` (fallback `true` + paste-as-text); `body` and FAQ answers
are Quill 2 `bubble` editors mounted on the canvas. A kind that gets a new field in the future
marks it in its own template — never a second renderer.

### D2. The panel is the old form minus the text
`_block_form.html` keeps the non-text fields per kind (survey select, phases rows, files,
map upload + colour + base map, results question + viz, event date/time/zone/seats/open,
button URL + style, video URL). Its heading field stays as a hidden input that the canvas
`h2` keeps in sync, so the panel form is always the complete block and ONE serialisation
goes to the server. Panels are rendered server-side for every block (hidden) plus one page
panel; selecting a block shows its panel — no fetch on select.

### D3. Write protocol
`POST .../blocks/<id>/` with `autosave=1` (FormData of the panel form + canvas values)
answers JSON: `{ok: true, block: <canvas shell HTML>, outline: <outline row HTML>}` or
`{ok: false, errors: {field: message}}` with 422. Settings posts (`.../settings/`) the same
way: `{ok, hero: <hero HTML>}`. The client swaps the fragment, keeps selection and, for text
edits, does not re-render the block being typed in (only on blur) so the caret never jumps.
Debounce 600 ms per block; blur flushes. Add (`.../blocks/add/`, kind only — creates a block
with empty data where valid, else with defaults) and delete and duplicate (new
`.../blocks/<id>/duplicate/`) are full posts that redirect to `#b-<id>` with `?select=<id>`.
Reorder stays JSON (`.../blocks/order/`), fed by both the canvas and the outline Sortable.

Default data per kind on add: text `{body: '<p></p>'}` skips the "write some text" rule when
`autosave=1` is absent and `kind` is being created from the library (an *empty* block is a
valid editing state on a canvas; the public page skips a text block with an empty body, a
documents block with no files, a map block with no area, a results block with no question,
an event block without a date — `page_blocks` already drops hidden survey cards the same way).

### D4. Publish popover
A Bootstrap dropdown anchored to the Publish button: address input + Copy, the
listed / unlisted switch (posts settings with `autosave=1`), QR links, and the publish /
unpublish form. The badge next to the title re-renders from the JSON answer.

### D5. Device toggle and preview
`.frame.mobile` sets the canvas to 390 px; block templates already reflow. *Preview* opens
`/p/<slug>/` in a new tab (a draft shows the member banner).

### D6. Roles and Pro
Unchanged: viewers and lapsed workspaces get the canvas read-only (no contenteditable, no
toolbars, no panel inputs); unpublish and delete keep working for editors.

## Risks / Trade-offs

- [Caret jumps while typing] → the block being edited is never re-rendered on an autosave
  answer; swaps happen on blur or when another block changed.
- [Rich text on the canvas bypasses the sanitiser] → the canvas only produces the POST body;
  `clean_block` → `coerce_creator_html` runs server-side as before; the swapped-in HTML is the
  server's.
- [Two Quill themes] → `snow` stays in the survey editor, `bubble` here; the catalog search
  tests do not care.
- [Empty blocks on the public page] → explicit skip rules per kind in `page_blocks`, tested.
