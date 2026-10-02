"""In-app changelog entries (change in-app-changelog, issue #227).

An entry is a file in `survey/changelog/`, written in the PR that ships the change it
describes, so an entry can never announce something that is not deployed. The body is HTML
like a customer-story body (`survey/stories.py`): no Markdown library is installed and the
repo review is the editor. Entries are English only.

File layout -- a header block of `key: value` lines between `---` fences, then the body:

    ---
    title: Empty sessions are now hidden
    kind: new
    link: editor_survey_responses
    image: changelog/2026-10-06-empty-sessions.png
    ---
    <p>Responses, Overview, Map and exports now leave out ...</p>

The id is the filename stem, `YYYY-MM-DD-slug`, so ids sort chronologically as plain strings
and a creator's seen-state is one watermark id (`CreatorPreferences.changelog_seen`): unseen
means `id > watermark`. The directory is read once per process; it only changes on deploy.
A malformed file raises here, and `ChangelogEntriesTest` loads every file in the directory,
so a bad entry fails CI rather than every editor page in production.
"""
import os
import re
from dataclasses import dataclass
from functools import lru_cache

ENTRIES_DIR = os.path.join(os.path.dirname(__file__), 'changelog')
ID_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$')
KINDS = ('new', 'fixed')
# URL prefixes of respondent surfaces: no card, icon or badge there, even for a
# signed-in creator looking at their own survey.
RESPONDENT_PREFIXES = ('/surveys/', '/r/')
FENCE = '---'


class ChangelogError(ValueError):
    """An entry file the loader refuses; the message names the file."""


@dataclass(frozen=True)
class Entry:
    id: str
    date: str          # 'YYYY-MM-DD', from the id
    title: str
    kind: str          # 'new' | 'fixed'
    body: str          # HTML, rendered |safe
    link: str = ''     # URL name the page offers as "Open ..."; '' = none
    image: str = ''    # static path under survey/assets/, '' = none


def _parse(path):
    name = os.path.basename(path)
    entry_id = os.path.splitext(name)[0]
    if not ID_PATTERN.match(entry_id):
        raise ChangelogError(
            f'{name}: filename must be YYYY-MM-DD-slug.html (lowercase, digits, hyphens)')
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    lines = text.split('\n')
    if not lines or lines[0].strip() != FENCE:
        raise ChangelogError(f'{name}: must start with a --- header block')
    try:
        end = lines.index(FENCE, 1)
    except ValueError:
        raise ChangelogError(f'{name}: header block is not closed with ---') from None
    header = {}
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        key, sep, value = raw.partition(':')
        if not sep:
            raise ChangelogError(f'{name}: header line without a colon: {raw!r}')
        header[key.strip()] = value.strip()
    title = header.get('title', '')
    if not title:
        raise ChangelogError(f'{name}: header needs a title')
    kind = header.get('kind', '')
    if kind not in KINDS:
        raise ChangelogError(f'{name}: kind must be one of {KINDS}, got {kind!r}')
    unknown = set(header) - {'title', 'kind', 'link', 'image'}
    if unknown:
        raise ChangelogError(f'{name}: unknown header keys {sorted(unknown)}')
    body = '\n'.join(lines[end + 1:]).strip()
    if not body:
        raise ChangelogError(f'{name}: body is empty')
    return Entry(
        id=entry_id, date=entry_id[:10], title=title, kind=kind, body=body,
        link=header.get('link', ''), image=header.get('image', ''),
    )


@lru_cache(maxsize=None)
def _load(directory):
    if not os.path.isdir(directory):
        return ()
    found = []
    for name in os.listdir(directory):
        if name.endswith('.html'):
            found.append(_parse(os.path.join(directory, name)))
    return tuple(sorted(found, key=lambda e: e.id, reverse=True))


def entries():
    """Every entry, newest first. Read once per process.

    `ENTRIES_DIR` is looked up at call time, not bound as a default, so a test
    can point the module at a temporary directory with `mock.patch`.
    """
    return _load(ENTRIES_DIR)


def latest():
    """The newest entry, or None when nothing has shipped yet."""
    found = entries()
    return found[0] if found else None


def unseen(seen_id):
    """Entries newer than the watermark, newest first. Empty watermark = everything."""
    return tuple(e for e in entries() if e.id > (seen_id or ''))


def clear_cache():
    """For tests that point the loader at a temporary directory."""
    _load.cache_clear()
