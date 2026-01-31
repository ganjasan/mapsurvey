## Context

The survey system uses hidden `<input>` elements to store GeoJSON data from map interactions. When users draw points, lines, or polygons on the map, the data is serialized and stored in these hidden inputs before form submission.

Currently, required geo-questions add the HTML5 `required` attribute to these hidden inputs. This causes browser validation to fail with "An invalid form control is not focusable" because browsers cannot display validation UI for hidden elements.

**Current code (leaflet_draw_button.html:13):**
```html
<input type="text" name="{{ widget.name }}" hidden class="geo-inp"
       {%if widget.required %} required {% endif %}>
```

## Goals / Non-Goals

**Goals:**
- Fix form submission for surveys containing required geo-questions
- Provide clear user feedback when required geo-fields are empty
- Maintain the requirement enforcement (users must still complete required fields)

**Non-Goals:**
- Changing the overall form submission flow
- Server-side validation changes (already exists)
- Modifying how geo data is stored or serialized

## Decisions

### Decision 1: Use data-attribute instead of required

Replace `required` with `data-required="true"` on hidden geo inputs.

**Rationale:** This preserves the intent (marking fields as required) while avoiding HTML5 validation constraints that don't work with hidden elements.

**Alternatives considered:**
- Make input visible but styled as hidden (`visibility: hidden`) - Still fails HTML5 validation
- Remove required entirely and rely on server-side - Poor UX, user loses all form data on validation failure

### Decision 2: Validate in existing form submit handler

Add validation logic to the existing `$("#section_question_form").submit()` handler in `base_survey_template.html`.

**Rationale:**
- Handler already exists and processes geo data before submission
- Single point of validation keeps code maintainable
- Can prevent submission with `e.preventDefault()`

### Decision 3: Visual feedback on the draw button

Highlight the draw button with a red border and show alert when validation fails.

**Rationale:** The draw button is the interactive element users associate with the geo question - highlighting it guides them to the action needed.

### Decision 4: Make option_group optional in admin

Add `blank=True` to the `option_group` ForeignKey in Question model.

**Rationale:** Questions that don't need choice options (text, number, geo types) should not require an option_group to be selected in Django admin. The field already has `null=True`, but without `blank=True` the admin form enforces selection.

## Risks / Trade-offs

**[Risk]** JavaScript disabled → Validation bypassed
→ Server-side validation already exists as fallback

**[Trade-off]** Alert-based error messaging is basic
→ Acceptable for MVP; can enhance with toast notifications later
