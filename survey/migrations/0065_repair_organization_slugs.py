import re

from django.db import migrations
from django.utils.text import slugify

# Deliberately duplicated from `survey.models` rather than imported. A migration
# has to keep running years after the model it repairs has moved on; importing
# a helper by name makes a future rename break `migrate` on a fresh database.
SLUG_RE = re.compile(r'^[-.\w]+\Z')


def _unique_slug(Organization, base, exclude_pk):
    base_slug = slugify(base)[:100] or 'org'
    slug = base_slug
    counter = 2
    while Organization.objects.filter(slug=slug).exclude(pk=exclude_pk).exists():
        suffix = f'-{counter}'
        slug = base_slug[:100 - len(suffix)] + suffix
        counter += 1
    return slug


def repair_slugs(apps, schema_editor):
    """Re-slugify organizations whose slug cannot appear in a URL.

    `org/(?P<slug>[-.\\w]+)/...` reverses to nothing for a slug with spaces or
    an apostrophe, and `{% url 'org_settings' active_org.slug %}` sits in the
    account dropdown of every base template -- so such a row is a 500 on every
    page its owner opens, the settings page that would fix it included. Two rows
    were in this state in production (ids 74 and 352); they are why this exists.
    """
    Organization = apps.get_model('survey', 'Organization')
    for org in Organization.objects.all().order_by('pk'):
        if org.slug and SLUG_RE.match(org.slug):
            continue
        # Derive from the slug they typed when there is one -- it is closer to
        # what they meant than the organization's auto-generated name.
        org.slug = _unique_slug(Organization, org.slug or org.name, org.pk)
        org.save(update_fields=['slug'])


def noop(apps, schema_editor):
    """Irreversible by design: the broken values carry no information worth
    restoring, and restoring them would re-break the owner's editor."""


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0063_respondent_file_uploads'),
    ]

    operations = [
        migrations.RunPython(repair_slugs, noop),
    ]
