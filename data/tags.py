"""Workspace tags (change data-tags, #673).

`set_tags` is the ONE writer — the dataset page, the survey settings panel, the REST endpoint and
the MCP tool call it: names are trimmed and capped, matched by slug, created on first use, and a tag
nothing carries any more is deleted. A survey's tags live on its canonical survey.
"""
from django.db import transaction
from django.utils.text import slugify

from data.models import Tag

MAX_TAGS = 10
MAX_NAME = 40


def clean_names(names):
    """Trimmed, de-duplicated (by slug) names, at most MAX_TAGS, each at most MAX_NAME characters."""
    if isinstance(names, str):
        names = names.split(',')
    out, seen = [], set()
    for raw in names or []:
        name = ' '.join(str(raw).split())[:MAX_NAME]
        slug = slugify(name, allow_unicode=True)[:50]
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append((name, slug))
    return out[:MAX_TAGS]


def _relation(obj):
    from data.models import Dataset
    if isinstance(obj, Dataset):
        return obj, 'datasets'
    canonical = obj.published_version or obj.canonical_survey or obj
    return canonical, 'surveys'


def tags_of(obj):
    """The item's tags, by name."""
    target, _rel = _relation(obj)
    return list(target.tags.all())


@transaction.atomic
def set_tags(org, obj, names):
    """Replace the tags of a dataset or a survey; returns the tag list."""
    target, rel = _relation(obj)
    wanted = []
    for name, slug in clean_names(names):
        tag, _created = Tag.objects.get_or_create(organization=org, slug=slug, defaults={'name': name})
        wanted.append(tag)
    previous = set(target.tags.values_list('pk', flat=True))
    target.tags.set(wanted)
    dropped = previous - {t.pk for t in wanted}
    if dropped:
        Tag.objects.filter(pk__in=dropped, datasets__isnull=True, surveys__isnull=True).delete()
    return wanted


def workspace_tags(org):
    """Every tag of the workspace, by name."""
    return list(Tag.objects.filter(organization=org).order_by('name'))
