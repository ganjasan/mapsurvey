"""Blog articles and the /blog/ feed (change public-blog-and-changelog, issue #647).

An article is a file in `survey/blog/`, written in the PR that ships what it describes -- the
rule `survey/changelog.py` set for changelog entries: publishing is a merge, and an article
cannot describe something that is not deployed. Customer stories stay `Story` rows (their
pictures and the customer's approval live outside the public repo); the feed reads both.

File layout -- a header block of `key: value` lines between `---` fences, then an HTML body:

    ---
    title: Budget questions: let residents split the money
    kind: feature
    summary: One or two sentences: the card lead and the meta description.
    cover: img/blog/2026-11-10-budget-questions/cover.png
    cover_alt: A budget question on a phone
    author: Mapsurvey
    topics: participatory-budgeting
    changelog: 2026-11-10-budget-questions
    ---
    <p>...</p>
    <img src="{static:img/blog/2026-11-10-budget-questions/split.png}" alt="...">

The filename is `YYYY-MM-DD-slug.html`: the date is the publication day, the slug the URL
(`/blog/<slug>/`). `{static:<path>}` tokens become static URLs at render time, so the manifest
hashes apply. A malformed file raises `BlogError` naming it; `BlogArticlesTest` loads the whole
directory, so a bad article fails CI and never a page in production.
"""
import datetime
import os
import re
from dataclasses import dataclass
from functools import lru_cache

ARTICLES_DIR = os.path.join(os.path.dirname(__file__), 'blog')
FILENAME = re.compile(r'^(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$')
STATIC_TOKEN = re.compile(r'\{static:([^}\s]+)\}')
# `{help:<key>}` = a help-centre URL from survey/help_links.py, so a renamed help page is
# one registry edit and HelpSiteLinksTest covers the link.
HELP_TOKEN = re.compile(r'\{help:([a-z0-9_]+)\}')
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
FENCE = '---'
DEFAULT_AUTHOR = 'Mapsurvey'

# kind -> (card/page label, filter value on /blog/?kind=). Stories are not articles; they get
# their filter value here so the feed has one table of chips.
KINDS = {
    'feature': ('Feature', 'features'),
    'idea': ('Idea', 'ideas'),
}
STORY_FILTER = ('Customer stories', 'stories')
REQUIRED = ('title', 'kind', 'summary')
OPTIONAL = ('cover', 'cover_alt', 'author', 'topics', 'changelog', 'updated', 'draft')


class BlogError(ValueError):
    """An article file the loader refuses; the message names the file."""


@dataclass(frozen=True)
class Article:
    id: str            # filename stem, 'YYYY-MM-DD-slug'
    slug: str
    date: datetime.date
    title: str
    kind: str
    summary: str
    body: str          # HTML with {static:} tokens unresolved
    cover: str = ''    # static path under survey/assets/
    cover_alt: str = ''
    author: str = DEFAULT_AUTHOR
    topics: tuple = ()
    changelog: tuple = ()   # changelog entry ids this article expands
    updated: datetime.date = None
    draft: bool = False

    @property
    def url(self):
        return f'/blog/{self.slug}/'

    @property
    def label(self):
        return KINDS[self.kind][0]


def _names(value):
    return tuple(part.strip() for part in value.split(',') if part.strip())


def _date(name, key, value):
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise BlogError(f'{name}: {key} must be an ISO date (YYYY-MM-DD), got {value!r}') from None


def _parse(path):
    name = os.path.basename(path)
    stem = os.path.splitext(name)[0]
    match = FILENAME.match(stem)
    if not match:
        raise BlogError(f'{name}: filename must be YYYY-MM-DD-slug.html (lowercase, digits, hyphens)')
    day = _date(name, 'filename date', match.group(1))
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')
    if not lines or lines[0].strip() != FENCE:
        raise BlogError(f'{name}: must start with a --- header block')
    try:
        end = lines.index(FENCE, 1)
    except ValueError:
        raise BlogError(f'{name}: header block is not closed with ---') from None
    header = {}
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        key, sep, value = raw.partition(':')
        if not sep:
            raise BlogError(f'{name}: header line without a colon: {raw!r}')
        header[key.strip()] = value.strip()
    unknown = set(header) - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        raise BlogError(f'{name}: unknown header keys {sorted(unknown)}')
    for key in REQUIRED:
        if not header.get(key):
            raise BlogError(f'{name}: header needs {key}')
    if header['kind'] not in KINDS:
        raise BlogError(f'{name}: kind must be one of {sorted(KINDS)}, got {header["kind"]!r}')
    topics = _names(header.get('topics', ''))
    from .topics import validate_slugs
    try:
        validate_slugs(topics)
    except ValueError as exc:
        raise BlogError(f'{name}: {exc}') from None
    changelog = _names(header.get('changelog', ''))
    if header.get('cover') and not header.get('cover_alt'):
        raise BlogError(f'{name}: a cover needs cover_alt')
    draft = header.get('draft', 'false').lower()
    if draft not in ('true', 'false'):
        raise BlogError(f'{name}: draft must be true or false')
    body = '\n'.join(lines[end + 1:]).strip()
    if not body:
        raise BlogError(f'{name}: body is empty')
    return Article(
        id=stem, slug=match.group(2), date=day, title=header['title'], kind=header['kind'],
        summary=header['summary'], body=body, cover=header.get('cover', ''),
        cover_alt=header.get('cover_alt', ''), author=header.get('author') or DEFAULT_AUTHOR,
        topics=topics, changelog=changelog,
        updated=_date(name, 'updated', header['updated']) if header.get('updated') else None,
        draft=draft == 'true',
    )


@lru_cache(maxsize=None)
def _load(directory):
    if not os.path.isdir(directory):
        return ()
    found = [_parse(os.path.join(directory, name))
             for name in os.listdir(directory) if name.endswith('.html')]
    slugs = [a.slug for a in found]
    dupes = sorted({s for s in slugs if slugs.count(s) > 1})
    if dupes:
        raise BlogError(f'two articles share the slug {dupes[0]!r}')
    return tuple(sorted(found, key=lambda a: a.id, reverse=True))


def articles():
    """Every article, drafts included, newest first. Read once per process."""
    return _load(ARTICLES_DIR)


def changelog_problems():
    """Changelog ids named by an article that are not entries, as 'file: id' strings.

    Checked by a test over the shipped directories rather than by the loader: the loader runs
    inside page renders (and inside tests that point the changelog at a temporary directory),
    where a missing entry should cost the link, not the page. Rendering ignores unknown ids."""
    from . import changelog
    entry_ids = {entry.id for entry in changelog.entries()}
    return [f'{a.id}.html: {i}' for a in articles() for i in a.changelog if i not in entry_ids]


def published():
    return tuple(a for a in articles() if not a.draft)


def by_slug(slug):
    return next((a for a in articles() if a.slug == slug), None)


def article_for_entry(entry_id):
    """The published article that expands a changelog entry, or None."""
    return article_map().get(entry_id)


def article_map():
    """{changelog entry id: published article} -- the reverse of the `changelog` header."""
    found = {}
    for article in reversed(published()):   # oldest first, so the newest article wins
        for entry_id in article.changelog:
            found[entry_id] = article
    return found


def render_body(article):
    """The body with `{static:<path>}` and `{help:<key>}` tokens resolved to URLs."""
    from django.templatetags.static import static
    from .help_links import help_urls
    urls = help_urls()
    body = STATIC_TOKEN.sub(lambda m: static(m.group(1)), article.body)
    return HELP_TOKEN.sub(lambda m: urls.get(m.group(1), '#'), body)


def asset_problems():
    """Static paths (cover, `{static:}`) with no file under survey/assets/ and `{help:}` keys
    not in the registry, as 'file: what' strings. Production serves static files through a
    manifest storage, where a missing file raises on render -- so a test over the shipped
    directory runs this, and a typo fails CI instead of the page."""
    from .help_links import HELP_LINKS
    bad = []
    for article in articles():
        paths = ([article.cover] if article.cover else []) + STATIC_TOKEN.findall(article.body)
        bad += [f'{article.id}.html: no static file {p}' for p in paths
                if not os.path.isfile(os.path.join(ASSETS_DIR, p))]
        bad += [f'{article.id}.html: unknown help key {k}' for k in HELP_TOKEN.findall(article.body)
                if k not in HELP_LINKS]
    return bad


def clear_cache():
    """For tests that point the loader at a temporary directory."""
    _load.cache_clear()


# --- the feed -------------------------------------------------------------------------------

@dataclass(frozen=True)
class FeedItem:
    kind: str          # 'story' | an article kind
    filter: str        # the ?kind= value that keeps it
    date: datetime.date    # None for a story with no publication date: listed last, undated
    title: str
    summary: str
    url: str
    story: object = None     # the Story row, for the story card
    article: Article = None


def filters():
    """[(value, label)] for the chips, in display order."""
    return [(STORY_FILTER[1], STORY_FILTER[0])] + [(f, label + 's') for label, f in KINDS.values()]


def feed_items(kind_filter=''):
    """Published stories and articles, newest first; `kind_filter` is a value of `filters()`."""
    from django.urls import reverse
    from .models import Story
    items = []
    if kind_filter in ('', STORY_FILTER[1]):
        for story in Story.objects.filter(is_published=True):
            day = story.published_date.date() if story.published_date else None
            items.append(FeedItem(kind='story', filter=STORY_FILTER[1], date=day, title=story.title,
                                  summary=story.summary, url=reverse('story_detail', args=[story.slug]),
                                  story=story))
    for article in published():
        value = KINDS[article.kind][1]
        if kind_filter in ('', value):
            items.append(FeedItem(kind=article.kind, filter=value, date=article.date,
                                  title=article.title, summary=article.summary, url=article.url,
                                  article=article))
    items.sort(key=lambda item: item.date or datetime.date.min, reverse=True)
    return items
