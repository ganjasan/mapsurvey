# Landing builder redesign — mockup

`builder.mockup.html` is a self-contained, clickable mockup of the landing page builder, v2.
Open it over HTTP (`python3 -m http.server` in this folder), not `file://`.

Screenshots: `mockup-1-editor.png` (editor, Timeline selected), `mockup-2-add-block.png`
(block library), `mockup-3-mobile-publish.png` (phone width, Publish popover, Event settings).

## What changes against the shipped builder (change landing-core)

| Shipped | Mockup | Borrowed from |
|---|---|---|
| A list of collapsed rows, each with a form behind "Edit" | The page itself is the editor: blocks render as visitors see them | Tilda, Squarespace Fluid Engine, Maptionnaire Project Pages |
| Text in a Quill box inside the form | Text is edited in place; a floating B / I / link / list toolbar appears on selection | Notion, Tilda |
| "Add block" button at the bottom only, Bootstrap modal | A "+" line appears between any two blocks on hover; the library has categories, icons and one-line descriptions, plus search | Tilda block library, Maptionnaire "Add section", Notion "/" menu |
| Reorder by dragging rows | Hover toolbar on each block: drag handle, up / down, duplicate, settings, delete | Squarespace, Tilda |
| Page settings and survey list stacked above the blocks in a left column | Left rail = outline of the page (click to jump, drag to reorder); right panel = settings of the selected block, or the page when nothing is selected | Tilda block panel, Webflow / Framer right inspector |
| Save button per form; errors re-render the whole page | Autosave with a "Saved just now" indicator; validation inline in the right panel | Editor autosave convention of this app |
| Publish = one button | Publish popover: address with copy, listed / unlisted switch, QR download, then "Publish now"; status badge next to the title | Framer / Webflow publish flow |
| No device preview | Desktop / phone toggle re-flows the canvas to 390 px | Carrd, Tilda breakpoints |
| Survey state visible only on the public page | Draft surveys get an orange dot in the outline and an inline note on the card | — |

## Rules kept from the Vision

One column, no grid, no fonts or colours per block, no custom HTML: the right panel holds
options that are not text (phases, seats, question, viz), the canvas holds the text.
