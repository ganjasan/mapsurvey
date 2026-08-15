# Tasks

- [x] 1.1 Convert the six multi-line `{# #}` blocks to `{% comment %}/{% endcomment %}`, wording
      unchanged: `_publishing_widget.html`, `activation_confirm.html`, `activation_failed.html`,
      `resend_activation_done.html`, `_faq_section.html`, `_landing_structured_data.html`.
- [x] 1.2 Add `TemplateCommentSyntaxTest` scanning `survey/templates/**/*.html` for a `{#` with no
      `#}` on the same line.
- [x] 1.3 Prove the guard works: red on the pre-fix templates (all six named), green after.
- [x] 1.4 `./run_tests.sh survey` — 1099 tests, OK (1 skipped). A second render-level test asserts
      no comment wording reaches the FAQ and JSON-LD partials.
- [x] 1.5 Verified in production after the deploy of 6dcdc61: a freshly created draft's editor
      navbar shows only the `Draft → v6` chip, and `/accounts/activate/resend/`, `/for-planners/`
      and `/for-researchers/` render (FAQ section included) with no comment text in the HTML.
