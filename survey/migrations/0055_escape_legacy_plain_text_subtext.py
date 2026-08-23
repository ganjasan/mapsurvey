"""Make existing subtext/subheading safe to render as HTML.

Question subtext used to be escaped on render; from this change on it is rendered
`|safe`, like the section subheading already was. Every row written before that
holds plain text, so a value containing `<`, `>` or `&` — "takes <5 minutes",
"R&D area" — would either vanish or render as broken markup once the template
stops escaping it.

This escapes exactly those legacy rows, once. `html` blocks are skipped: their
subtext has always been the block's markup. Rows that already contain creator
markup are skipped too, so a re-run cannot double-escape (the migration is
written to be safely re-runnable even though Django will only apply it once).
"""

from django.db import migrations
from django.utils.html import escape


NEEDS_ESCAPING = ('<', '>', '&')


def _escape_field(model, field, extra_filter=None):
    rows = model.objects.all()
    if extra_filter:
        rows = rows.exclude(**extra_filter)
    updates = []
    for row in rows.iterator():
        value = getattr(row, field)
        if not value or not any(ch in value for ch in NEEDS_ESCAPING):
            continue
        from survey.html_sanitize import _RICH_TEXT_MARKER
        if _RICH_TEXT_MARKER.search(value):
            continue  # already rich text — leave it alone
        setattr(row, field, escape(value))
        updates.append(row)
    if updates:
        model.objects.bulk_update(updates, [field], batch_size=500)


def escape_legacy_plain_text(apps, schema_editor):
    # Formatted Text blocks are excluded by input_type; their subtext is markup
    # by definition and predates nothing.
    _escape_field(apps.get_model('survey', 'Question'), 'subtext',
                  extra_filter={'input_type': 'html'})
    _escape_field(apps.get_model('survey', 'QuestionTranslation'), 'subtext',
                  extra_filter={'question__input_type': 'html'})
    # Section subheading was already rendered |safe, so its rows are already
    # interpreted as markup — touching them would change what is on the page.


def noop_reverse(apps, schema_editor):
    """Escaping is not reversed: un-escaping would reintroduce the raw
    characters into a field that is rendered |safe."""


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0054_section_subheading_unbounded'),
    ]

    operations = [
        migrations.RunPython(escape_legacy_plain_text, noop_reverse),
    ]
