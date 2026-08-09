# Multi-line `{# #}` template comments render into the page

**Type**: bug
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-05

## Description

Django's `{# ... #}` comment syntax is **single-line only**. A comment spanning more than one line is
not stripped — it is emitted verbatim into the rendered HTML.

Five templates carry multi-line `{# #}` comments, and at least two of them ship developer commentary
to real visitors. Confirmed by fetching `/for-planners/`, which returns:

```
{# Per-page structured data for SEO landings. FAQPage + BreadcrumbList are
{# Visible FAQ section for SEO landing pages. Renders nothing when n
```

Affected:

- `survey/templates/partials/_landing_structured_data.html:1` — every SEO landing page
- `survey/templates/partials/_faq_section.html:2` — every SEO landing page
- `survey/templates/django_registration/activation_confirm.html:13`
- `survey/templates/django_registration/resend_activation_done.html:12`
- `survey/templates/django_registration/activation_failed.html:14`

The landing-page ones are the ones that matter: those pages exist to be crawled, and they are
currently serving stray internal notes about how the JSON-LD is built.

## Notes

- Found 2026-08-05 while verifying `closed-survey-edit-path` by hand. I had written the same defect
  into `survey_detail.html` a minute earlier and only caught it because the banner was inspected in
  a browser rather than trusted — which is also the argument for doing that check.
- Fix is mechanical: `{% comment %}...{% endcomment %}` for anything multi-line, or collapse to one
  line. Five files.
- Worth a guard rather than only a fix, since nothing catches this today. A test that renders each
  template and asserts no `{#` survives would do it, or a check in whatever lint step exists.
- Not folded into `closed-survey-edit-path`: those templates are unrelated to that change, and a
  fix touching SEO landing output belongs on its own commit where it can be reviewed as such.
