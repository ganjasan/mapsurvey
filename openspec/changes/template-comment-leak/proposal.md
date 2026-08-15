## Why

Django's `{# ... #}` comment is **single-line only**. A `{#` whose `#}` sits on a later line is not
parsed as a comment at all — the whole block is rendered into the page as visible text.

Six templates carry multi-line `{# #}` blocks, and every one of them leaks onto a page:

- `editor/partials/_publishing_widget.html:12` — leaked into the editor navbar next to a draft's
  status chip. Spotted in production today, in the shipped `draft-results-scope` change.
- `django_registration/activation_confirm.html:13`, `activation_failed.html:14`,
  `resend_activation_done.html:12` — the account-activation pages, i.e. the first three screens a
  new signup can hit.
- `partials/_faq_section.html:2`, `partials/_landing_structured_data.html:1` — every SEO landing
  page that renders an FAQ, including the text that ends up next to the JSON-LD block.

The failure is silent: no template error, no failing test, no lint. It reads correctly in the editor
because the single-line form looks identical.

## What Changes

- Convert all six multi-line `{# #}` blocks to `{% comment %}/{% endcomment %}`. Comment wording is
  preserved verbatim; no rendered markup changes other than the leaked text disappearing.
- Add `TemplateCommentSyntaxTest`, which walks `survey/templates/**/*.html` and fails on any `{#`
  without a `#}` on the same line, naming every offender. Verified red against the current templates
  (all six reported) and green after the conversion.

## Impact

- Affected specs: none — no behaviour is specified here, this is a rendering defect.
- Affected code: six templates under `survey/templates/`, plus one test.
- No migration, no model or view change.
