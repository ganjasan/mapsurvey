# Tasks — subtext reaches the respondent

- [x] 1.1 Carry `sublabel` onto the widget for answerable types in both form paths
      (`single_question_form`, `__init__`).
- [x] 1.2 `question_subtext` template filter.
- [x] 1.3 Render the helper line after the label in `survey_section_partial.html` (scale and card
      branches) and `question_preview_frame.html`.
- [x] 1.4 `image`: pass the subtitle through `ShowImageField` and render it as a caption in
      `show_image.html`. Needed one more step than expected — `ShowImageWidget.get_context`
      copies named attrs onto the template context one by one, so the subtitle had to be added
      there too or the template saw nothing.
- [x] 1.5 CSS block; collectstatic.
- [x] 2.1 Table test over every `INPUT_TYPE_CHOICES` entry asserting name/subtext shown-vs-dropped.
      Its first version failed on a marker, not on the code: `name="q_text"` also matches the
      card wrapper's `data-field-name="q_text"`, which sits earlier in the page — now keyed on
      the input's id.
- [x] 2.2 Live-preview endpoint shows subtext for an unsaved draft.
- [x] 2.3 `./run_tests.sh survey` green.
- [x] 3.1 Spec delta; backlog #123 struck through; commit, push, PR.
