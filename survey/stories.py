"""Customer stories (change customer-stories-showcase): body image tokens.

A story body is HTML written in the repo and carries its pictures as `{img:<key>}`
tokens instead of URLs, so the same text works on production (`media/`), on a PR
preview (`previews/mapsurvey-pr-N/media/`) and on a laptop (`/mediafiles/`). The
tokens are resolved here, against the story's `StoryImage` rows, at render time.
"""
import re

IMAGE_TOKEN = re.compile(r'\{img:([A-Za-z0-9_-]+)\}')


def image_urls(story):
    """{key: url} for every picture the story owns."""
    return {img.key: img.image.url for img in story.images.all() if img.image}


def render_body(story):
    """The story body with every `{img:key}` replaced by that picture's URL.

    An unknown key becomes an empty string — a broken picture, never a 500 on a
    public page.
    """
    urls = image_urls(story)
    return IMAGE_TOKEN.sub(lambda m: urls.get(m.group(1), ''), story.body or '')
