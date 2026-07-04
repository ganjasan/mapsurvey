# Tasks — simplify-survey-create

## 1. Implementation

- [x] 1.1 `SurveyCreateForm` in `survey/editor_forms.py`: `ModelForm` over
      `SurveyHeader` with `fields = ['name']` (same TextInput widget as
      `SurveyHeaderForm`); `SurveyHeaderForm` stays as-is for the settings panel
- [x] 1.2 `editor_survey_create` uses `SurveyCreateForm`; map hidden-field
      handling, owner collaborator, and default first section unchanged; drop
      the now-unused `basemap_choices` from the create context
- [x] 1.3 Rewrite `survey_create.html`: `.pr-card` with the name `.pr-field`
      ("e.g. Park improvements" placeholder), "Where is your survey area?"
      map section (same picker JS), `.pr-switch` for auto-center, Create/Cancel,
      and a `.pr-help` hint pointing to Survey settings for everything else

## 2. Verification

- [x] 2.1 Tests: creating with name only yields model defaults
      (visibility=private, redirect `#`, basemaps all three, empty
      thanks/languages) and redirects to Build; map lat/lng/zoom still saved
      when posted
- [x] 2.2 Existing create tests still pass (they post only `name` + map
      fields — now the canonical shape)
- [x] 2.3 Manual: create a survey via the new page, open Survey settings,
      confirm all deferred fields are editable there
