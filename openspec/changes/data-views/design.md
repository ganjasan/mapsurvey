## Decisions

1. **A view is a row over a dataset**, never over rows: `DatasetView(dataset, name, kind, conditions,
   fields, color)`. Its id is stable across versions (#671), because it names fields, not objects.
   `kind` is `objects` for layer datasets and `grid` for answers datasets — the privacy class
   decides, not the creator.
2. **Links carry the view.** `DatasetLink.view` (null = the whole dataset). The survey still resolves
   the dataset's layer through `layers_for`; the map metadata swaps the layer's style colour for the
   view's, and the gated GeoJSON endpoint and the object card filter through the view. A Site map
   block stores `view` next to `dataset`.
3. **Filtering in SQL**: conditions become `properties__<field>` lookups (`exact`, `in`, `gt`, `lt`;
   numbers compared as numbers when the value is numeric) on `LayerObject`; the collection is built
   with the same streamed feature builder the layer cache uses (`layers._feature_json`), keeping only
   the view's fields, cached per (view, layer.updated_at, view.updated_at). A survey link already
   keeps the layer within the survey caps, so a view (a subset) does too.
4. **Grid views** take `data.features.question_features` over `SessionScope.public` sessions and
   `data.aggregate.grid` with K = the survey's public-results threshold (default 3); the response is
   cell polygons with a masked count, nothing else. `link_refusal` refuses a grid view in a survey.
5. **Privacy**: conditions and fields may name public fields only (a condition on a private field
   would let the map answer questions about it); views of a private dataset follow the dataset's
   own link refusal (public only).

## Risks

- One survey shows one view of a dataset (the link is unique per dataset and survey). Two views of
  the same dataset on one survey wait for a need.
