## Decisions

### D1. The panel form stays the carrier
Every value still posts from the block's panel form (`_block_form.html`), so `_save_block` and
`clean_block` are unchanged. Primary fields there become hidden inputs; the canvas controls write into
them before each autosave (`syncBlock`): contenteditable `[data-field]` (text), inline inputs
`[data-input="<name>"]` (link, date, select), files through `DataTransfer` into the panel's hidden file
input of the same name, list rows `[data-rows]` rebuilt into hidden `q`/`a`, `phase_*`, `current` inputs
in a `.lb-row-sink`.

### D2. One inline partial
`landings/editor/_inline.html` holds the per-kind canvas editors; `_canvas_block.html` includes it in
place of the public template for documents, FAQ and timeline (they are edited row by row), and next to
it (empty state or under the content) for the other kinds. The public templates are untouched.

### D3. Files
Image and map: a drop zone in the empty block, a *Replace* button over a set one; drop or choose →
copied into the panel input → saved at once. Documents: drop zone under the list adds; × on a row sets
the panel's hidden `remove_<id>`; titles are `data-field="file_title_<id>"`.

### D4. Lists
FAQ rows: question (plain contenteditable) + answer (Quill snow, the help-text toolbar, shown while the
answer has focus) + ×; *Add a question* clones a `<template>`. Timeline rows: when, title, text (plain)
+ *Now* toggle (one at a time) + ×; *Add a phase*. Rows with nothing typed are dropped by the cleaner.
