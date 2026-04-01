## 1. Model & Migration

- [x] 1.1 Add `use_geolocation = models.BooleanField(default=False)` to `SurveySection` in `survey/models.py` (after line 341)
- [x] 1.2 Run `makemigrations` to generate AddField migration

## 2. Frontend Geolocation JS

- [x] 2.1 Add geolocation block to `survey/templates/base_survey_template.html` after map init (line 123)
  - Template variable `{{ section.use_geolocation|yesno:"true,false" }}`
  - `locateUser()` function using `navigator.geolocation.getCurrentPosition`
  - Auto-call on page load when enabled
  - Blue circleMarker at user position
  - Options: `enableHighAccuracy: true, timeout: 10000, maximumAge: 300000`
- [x] 2.2 Add "Locate me" custom Leaflet control button (bottomright, safe DOM creation)

## 3. Editor Integration

- [x] 3.1 Add `use_geolocation` to `SurveySectionForm` fields and widgets in `survey/editor_forms.py`

## 4. Serialization

- [x] 4.1 Add `"use_geolocation": section.use_geolocation` to export in `survey/serialization.py` (serialize_sections)
- [x] 4.2 Add `use_geolocation=section_data.get("use_geolocation", False)` to import in `survey/serialization.py` (SurveySection.objects.create)

## 5. Versioning

- [x] 5.1 Add `use_geolocation=section.use_geolocation` to clone in `survey/versioning.py` (clone_survey_for_draft)

## 6. Tests

- [x] 6.1 Add serialization roundtrip test with `use_geolocation=True`
- [x] 6.2 Add test: import without `use_geolocation` key defaults to `False`
