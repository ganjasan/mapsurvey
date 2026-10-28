## ADDED Requirements

### Requirement: The visible order and the object rows never disagree

The object editor SHALL keep its two pieces of list state in step: the order of keys
currently passing the filter, and the map from key to the row data behind it. Whenever the
editor replaces or removes object rows, it MUST bring the order back in step with the map
before any code path can repaint the list, and a render MUST NOT dereference a row that is
absent from the map.

#### Scenario: Objects are replaced after an import

- **WHEN** an import finishes and the editor reloads the layer's objects, replacing every
  row it holds
- **THEN** the visible order is recomputed from the newly loaded rows at the same moment,
  before the editor requests the layer geometry
- **AND** a scroll of the list, a window resize or a row click while the geometry request
  is still in flight repaints the list without raising an exception

#### Scenario: The selected object is deleted

- **WHEN** the creator deletes the object currently open in the card
- **THEN** its key is gone from the visible order before the card closes and repaints the
  list
- **AND** the deletion completes and reports success, rather than reporting an error with
  the row still on screen

#### Scenario: A key in the order has no row behind it

- **WHEN** the list renders a position whose key is absent from the object rows
- **THEN** that position is skipped and the remaining rows render
- **AND** no exception reaches the browser's error handler

### Requirement: A failed list render is never silent

A render failure in the object editor SHALL NOT leave the creator with a half-painted list
and no indication that anything went wrong.

#### Scenario: The list cannot render a row

- **WHEN** the list encounters a position it cannot render
- **THEN** the editor continues to accept selection, filtering and editing of the objects
  it can render
