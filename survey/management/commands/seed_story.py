"""Install or refresh one customer story from the repo (change customer-stories-showcase).

    python manage.py seed_story olney-white-squirrel-count
    python manage.py seed_story olney-white-squirrel-count --draft

The story lives in survey/story_data/<slug>/: `story.json` (every scalar field, the
cover/card/logo file names and `images: {key: file}`), `body.html` (the body, with
pictures as `{img:key}` tokens) and `images/`. The repo is the source of truth; a
re-run overwrites what an admin edited, keeps the row's id and its first
`published_date`, and re-uploads the pictures (the public storage never overwrites
a key, so each run gets fresh names and the row is pointed at them).

Why a command and not a data migration: the story is refreshed after the October
count and whenever the City asks for a change; a migration is one-shot and would
carry the images every time.
"""
import json
from datetime import datetime
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from survey.models import Story, StoryImage

DATA_ROOT = Path(__file__).resolve().parents[2] / 'story_data'
SCALAR_FIELDS = (
    'title', 'story_type', 'place', 'sector', 'summary', 'credit', 'credit_note',
    'cover_alt', 'cover_credit', 'facts',
)
FILE_FIELDS = {'cover': 'cover_image', 'card_image': 'card_image', 'credit_logo': 'credit_logo'}


def story_dir(slug):
    return DATA_ROOT / slug


def load_story_data(slug):
    """(meta dict, body html) for a slug, or CommandError when the directory is missing."""
    base = story_dir(slug)
    if not (base / 'story.json').is_file():
        raise CommandError(f"No story data at {base.relative_to(DATA_ROOT.parents[1])}.")
    meta = json.loads((base / 'story.json').read_text(encoding='utf-8'))
    body = (base / 'body.html').read_text(encoding='utf-8') if (base / 'body.html').is_file() else ''
    return meta, body


def _attach(field_file, base, filename, slug):
    """Store `images/<filename>` under stories/<slug>/ and point the field at it."""
    path = base / 'images' / filename
    if not path.is_file():
        raise CommandError(f'Missing image {path.name} for {slug}.')
    with path.open('rb') as fh:
        field_file.save(f'{slug}/{path.name}', File(fh), save=False)


class Command(BaseCommand):
    help = 'Install or refresh a customer story from survey/story_data/<slug>/.'

    def add_arguments(self, parser):
        parser.add_argument('slug')
        parser.add_argument('--draft', action='store_true',
                            help='Leave the story unpublished (is_published=False).')

    def handle(self, *args, **opts):
        slug = opts['slug']
        meta, body = load_story_data(slug)
        base = story_dir(slug)

        with transaction.atomic():
            story, created = Story.objects.get_or_create(slug=slug, defaults={'title': meta['title']})
            for name in SCALAR_FIELDS:
                if name in meta:
                    setattr(story, name, meta[name])
            story.body = body
            story.is_published = not opts['draft']
            if not story.published_date:
                stamp = meta.get('published_date')
                story.published_date = (
                    timezone.make_aware(datetime.fromisoformat(stamp)) if stamp else timezone.now())
            for key, field in FILE_FIELDS.items():
                if meta.get(key):
                    _attach(getattr(story, field), base, meta[key], slug)
            story.save()

            wanted = meta.get('images') or {}
            story.images.exclude(key__in=wanted).delete()
            for key, filename in wanted.items():
                image = StoryImage.objects.filter(story=story, key=key).first() or StoryImage(story=story, key=key)
                _attach(image.image, base, filename, slug)
                image.save()

        verb = 'installed' if created else 'refreshed'
        state = 'draft' if opts['draft'] else 'published'
        self.stdout.write(self.style.SUCCESS(
            f'Story {verb} ({state}): /stories/{story.slug}/ with {len(wanted)} body image(s).'))
