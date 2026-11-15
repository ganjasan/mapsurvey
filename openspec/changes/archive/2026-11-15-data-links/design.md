## Decisions

1. **A link is a row, and the resolver reads it.** `data.models.DatasetLink(dataset, survey | site_block,
   fields)`. `survey.layers.layers_for(survey)` returns the canonical survey's own layers plus the
   layers of the public datasets linked to it (a subquery on ids, so an owned layer is never
   duplicated by the join). Every read surface that already goes through `layers_for` — respondent
   map metadata, the question layer picker, Responses, print, the ZIP — follows without a change;
   write paths (layer settings, object editor, layer service, REST/MCP layer writes) keep resolving
   OWNED layers only, so a survey cannot edit or delete a dataset it borrows. The gated endpoint
   resolves through `layers_for`.
2. **The survey is the canonical one** (`layer_owner`), like layer ownership: drafts and versions
   borrow its links.
3. **Field choice per link** narrows the object card only (`object_card_payload(only=…)`); the
   layer GeoJSON keeps the public fields (styles and labels match raw names).
4. **Site map block** stores `dataset` (id) next to `area`; `services.sites.save_block` keeps the
   block's `DatasetLink` in step; the public page and the builder canvas fetch
   `/p/<slug>/blocks/<id>/dataset.geojson` (same access as the page, `cached_geojson_response`).
5. **Used by** = links + questions bound to the layer + the owning survey; one function
   `data.links.used_by(dataset)` feeds the dataset page, the delete page and the catalogue count.
6. **Delete** is offered for workspace uploads only (a survey layer is deleted in its survey). It
   is a page listing every place first, then a POST; it is refused while a question is bound
   (`Question.layer` is PROTECT and the survey would lose its question), and removes links and
   empties site blocks otherwise.
7. **Guards live in `data.links`** (`link_refusal`) so the survey card and the site block refuse
   for the same reasons in the same words.

## Risks

- Layer settings (colour, style, label field) live on the layer, so they are shared by every
  survey that links it; the card shows a linked layer read-only with "Open in Data".
- The ZIP export of a survey copies linked layers; an import makes them the new survey's own.
