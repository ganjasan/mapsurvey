## Decisions

1. **One table, relations per module.** `data.models.Tag(organization, name, slug)` unique per
   workspace by slug, with `datasets` and `surveys` many-to-many relations declared on the tag (the
   survey app gains no migration). Sites, map apps and reports add one relation each when they need it.
2. **One writer**, `data.tags.set_tags(org, obj, names)`: names are trimmed, capped (10 tags,
   40 characters), matched by slug (so "Riverside 2027" and "riverside-2027" are one tag), created on
   first use; tags nothing carries any more are deleted. The editor views, the REST endpoint and the
   MCP tool all call it.
3. **A survey's tags live on the canonical survey**; drafts and versions answer with it.
4. **Filters are links** (`?tag=<slug>`), like the catalogue's other filters.
5. **Who**: tagging a dataset follows the dataset page's edit rule; tagging a survey needs the editor
   role on it (the API's `deps.survey(role='editor')`).
