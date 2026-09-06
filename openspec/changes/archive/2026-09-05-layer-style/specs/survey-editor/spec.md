## MODIFIED Requirements

### Requirement: Reference layers card in Survey settings
Survey settings SHALL include a "Reference layers" card (after "Respondent map")
showing each layer as a card with color swatch, name, object count and attachment summary,
an "Open editor" action leading to the layer's object editor, an edit state exposing a
*Style* block (base: colour, opacity, line width, point size, point icon; a "Style by
attribute" switch with property picker, categories / graduated mode, an editable class
table with colour, width, icon and legend label per class, an "other" class, an
"Auto-fill from data" action and a "Show legend to respondents" switch, with a live
preview of the layer), label field, key field (both pickable from the objects' property
names) and the info-popups toggle, plus a delete action and a "New layer" action. A
`question` layer's card SHALL show a "source: answers" badge naming the geo question and
the "Objects on the map" question(s) using it, SHALL expose only name and the base style
in its edit state, SHALL offer no upload/draw actions, and its "Open editor" SHALL open the
object editor read-only. The card SHALL NOT create `question` layers — they are created
from the Objects-on-the-map question form. Layer operations SHALL save via dedicated
endpoints and reflect results without a page reload; a style that fails normalisation
SHALL be reported on the card with the reason. Deleting a layer bound to a `layer_objects`
question SHALL be refused with a message naming the question. The card SHALL be visible to
owners only and absent when the kill switch is off.

#### Scenario: Open the editor from the card
- **WHEN** the owner clicks "Open editor" on a layer card
- **THEN** the object editor for that layer opens

#### Scenario: New layer goes straight to the editor
- **WHEN** the owner clicks "New layer"
- **THEN** an empty layer is created and its object editor opens in the empty state

#### Scenario: Bound layer cannot be deleted
- **WHEN** the owner clicks delete on a layer bound to a `layer_objects` question
- **THEN** the card shows a message naming the question and the layer remains

#### Scenario: Question layer card points at the question
- **WHEN** the owner opens the card of a layer sourced from `Q1`, used by "Marks by other residents"
- **THEN** the card shows the badge, names both, offers name and base style, and no label/key/popup fields, rule editor or upload zone

#### Scenario: Auto-fill a categories rule
- **WHEN** the owner switches on "Style by attribute", picks `priority_class` and clicks Auto-fill
- **THEN** the table lists the four values with counts, distinct colours and widths, and saving stores the rule

#### Scenario: Style saves without a reload
- **WHEN** the owner changes the base opacity
- **THEN** the card preview updates and the status reads Saved
