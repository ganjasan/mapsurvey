## 1. Picker

- [x] 1.1 `QuestionForm`: in a Form section record the removed map types with their label and the reason in `input_type.unavailable_types`
- [x] 1.2 `picker_groups_for(choices, unavailable)` returns them with `disabled`/`reason`; the template tag passes the field's `unavailable_types`
- [x] 1.3 Picker template renders disabled types as inert `.qtp-off` tiles (no `.qtp-card`, no `data-qtp-value`) and the reason under the group; CSS
- [x] 1.4 Section settings: Layout help text says a Form section cannot hold map questions

## 2. Tests

- [x] 2.1 Unit: `picker_groups_for` with `unavailable`
- [x] 2.2 View: new-question modal in a Form section shows disabled map tiles + reason; Map section shows none
