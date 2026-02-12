## Context

Survey questions render inside `#info_page` — a narrow sidebar (max 480px, 85% on mobile) overlaying a full-screen Leaflet map. Currently `survey_section.html` calls `{{ form.as_p }}` which dumps all fields as flat `<p>` elements with no grouping. Geo questions (point/line/polygon) already render as styled buttons via custom widget templates (`leaflet_draw_button.html`), but text, choice, and other input questions have no visual structure.

The form is a Django `SurveySectionAnswerForm` that dynamically creates fields based on question `input_type`. Each field's widget already renders its own template (e.g. `RadioSelect` for choice, `CheckboxSelectMultiple` for multichoice, `PointDrawButtonWidget` for point). Subquestion forms for geo popups are serialized separately via `.as_p()` in the view (line 366 of `views.py`) — these stay unchanged.

## Goals / Non-Goals

**Goals:**
- Each input-bearing question rendered in a visually distinct card
- Custom radio button and checkbox styling with 44px touch targets
- Consistent spacing rhythm between cards and geo buttons
- Works within the existing 480px sidebar constraint and mobile 85% width

**Non-Goals:**
- Redesigning the overall sidebar layout or navigation buttons
- Changing geo button widget design (already has good styling)
- Touching subquestion forms that render inside Leaflet popups — they use `.as_p()` and are serialized as HTML strings in JS
- Adding new Django form widgets or changing form field types
- Responsive breakpoints beyond what already exists

## Decisions

### 1. Replace `form.as_p` with field-by-field template iteration

**Choice**: Iterate `form` fields in `survey_section.html` using `{% for field in form %}`, wrapping each in a `<div class="question-card">`.

**Alternative considered**: Custom `as_cards()` method on the form class — rejected because it mixes presentation logic into Python code and makes it harder to apply conditional CSS classes per input type.

**Implementation**: Each field exposes `field.field.widget` which has a class name we can check. However, Django template language doesn't support `isinstance`. Instead, we'll add a custom `input_type` attribute to each widget in `SurveySectionAnswerForm.__init__` so the template can use `{% if field.field.widget.input_type %}` for conditional wrapping.

The template will:
- Wrap fields where `input_type` is in `{text, text_line, number, choice, multichoice, range}` in `.question-card`
- Render `rating` fields with `.question-card-inline` (no card, horizontal layout)
- Render geo/html/image fields without card wrapper (their widget templates already provide structure)

### 2. Expose `input_type` on widget instances

**Choice**: In `SurveySectionAnswerForm.__init__`, after creating each field, set `self.fields[field_name].widget.input_type = question.input_type`. This is a simple attr — no widget subclass changes needed.

The template checks this via `field.field.widget.input_type`. We'll also create a custom template filter `is_card_question` that checks if the input_type is in the card set, to keep the template clean.

### 3. CSS-only custom radio and checkbox

**Choice**: Hide native `<input type="radio">` and `<input type="checkbox">` with `opacity: 0; position: absolute;`, style the `<label>` with a pseudo-element circle/square, and use `:checked + label` for the selected state. This works with Django's `RadioSelect` and `CheckboxSelectMultiple` output without any widget template changes.

**Rationale**: CSS-only approach means no JS, no custom widget templates, and full compatibility with existing form serialization and prepopulation logic.

**Details**:
- Radio: `::before` pseudo-element — 20px circle, 2px border. On `:checked`, inner fill with scale animation
- Checkbox: `::before` pseudo-element — 20px square, 2px border, rounded corners. On `:checked`, checkmark via `::after` or border trick
- Label: `padding-left: 32px`, `min-height: 44px`, `display: flex; align-items: center` for WCAG touch target
- Colors: `#333` border, `#1a73e8` fill on checked (standard accessible blue)

### 4. Card visual treatment

**Choice**: White background, `12px` padding, `8px` border-radius, `1px solid #e0e0e0` border. No box-shadow — keeping it flat and utilitarian to match the field-survey context. `12px` margin-bottom between cards.

**Alternative considered**: Subtle shadow (`0 1px 3px rgba(0,0,0,0.1)`) — rejected because inside the sidebar with its own border, shadows create visual noise. A clean border is enough separation.

### 5. Geo button alignment

**Choice**: Add `border-radius: 8px` to `.drawbutton` to match card corners, and ensure margin-bottom matches card spacing (`12px`). No other changes to geo buttons.

## Risks / Trade-offs

- **Subquestion forms in popups are unaffected** — they render via `.as_p()` serialized in JS. The custom radio/checkbox CSS will still apply inside popups since the CSS selectors are global, which is actually a benefit (consistent look in popups too). → No mitigation needed, this is a positive side effect.
- **Django RadioSelect HTML structure** — Django renders `<ul><li><label><input>...</label></li></ul>`. The CSS selectors must target this exact structure. → Verify against Django 3.x / 4.x RadioSelect output; it's stable across versions.
- **`form.errors` display** — `as_p()` handles error rendering. With manual field iteration, we need to render `{{ field.errors }}` explicitly inside each card. → Template includes `{{ field.errors }}` before the field widget.
- **Hidden fields** — `form.as_p()` handles hidden fields automatically. Manual iteration must use `{{ form.hidden_fields }}` separately. → Render hidden fields outside the card loop via `{% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}`.
