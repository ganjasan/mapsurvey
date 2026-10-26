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

Two tiers (change changelog-hero, #423). The default `tier: card` is the small corner card.
`tier: hero` is the promotional banner on the dashboard for the biggest changes: a plate
(`art`, or `image`), one call to action (`link` + `link_query`, `cta_label`), an optional
help link (`help`, a HELP_URL key), example prompts (`chips`, `|`-separated, `{survey}` =
one of the creator's survey names) and an audience (`show_if`, `note_if` + `note`: names
from `changelog_audience.PREDICATES`). A hero is *pending* for a creator while it is unseen,
at most `HERO_LIFETIME_DAYS` old and its audience holds; a pending hero suppresses the small
card everywhere, and a hero never renders as a small card. Any two heroes are at least
`HERO_MIN_SPACING_DAYS` apart -- a test over the shipped directory, not a convention.
"""
import datetime
import os
import re
from dataclasses import dataclass
from functools import lru_cache

from .changelog_audience import PREDICATES

ENTRIES_DIR = os.path.join(os.path.dirname(__file__), 'changelog')
ID_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$')
KINDS = ('new', 'fixed')
TIERS = ('card', 'hero')
# Plate styles the hero partial knows how to draw (`_whats_new_hero.html`).
ARTS = ('agent',)
HERO_LIFETIME_DAYS = 30
HERO_MIN_SPACING_DAYS = 14
CARD_KEYS = {'title', 'kind', 'link', 'image', 'tier'}
HERO_KEYS = CARD_KEYS | {'art', 'eyebrow', 'link_query', 'cta_label', 'help', 'chips',
                         'show_if', 'note_if', 'note'}
CHIP_PLACEHOLDER = '{survey}'
# URL prefixes of respondent surfaces: no card, icon or badge there, even for a
# signed-in creator looking at their own survey. `/oauth/` is the consent page
# (change oauth-server): a creator mid-sign-in for ChatGPT is not reading news.
RESPONDENT_PREFIXES = ('/surveys/', '/r/', '/oauth/')
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
    tier: str = 'card'
    # Hero only (change changelog-hero). Empty / () on a card.
    art: str = ''
    eyebrow: str = ''
    link_query: str = ''    # appended to the resolved link: 'from=dashboard'
    cta_label: str = ''
    help: str = ''          # HELP_URL key of the secondary "How it works" link
    chips: tuple = ()
    show_if: tuple = ()     # predicate names, all must hold
    note_if: str = ''       # predicate name; '' = the note always shows (if any)
    note: str = ''

    @property
    def is_hero(self):
        return self.tier == 'hero'

    @property
    def day(self):
        return datetime.date.fromisoformat(self.date)


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
    tier = header.get('tier', 'card')
    if tier not in TIERS:
        raise ChangelogError(f'{name}: tier must be one of {TIERS}, got {tier!r}')
    allowed = HERO_KEYS if tier == 'hero' else CARD_KEYS
    unknown = set(header) - allowed
    if unknown:
        raise ChangelogError(f'{name}: unknown header keys {sorted(unknown)}'
                             + ('' if tier == 'hero' else ' (hero keys need tier: hero)'))
    body = '\n'.join(lines[end + 1:]).strip()
    if not body:
        raise ChangelogError(f'{name}: body is empty')
    extra = _parse_hero(name, header, kind) if tier == 'hero' else {}
    return Entry(
        id=entry_id, date=entry_id[:10], title=title, kind=kind, body=body,
        link=header.get('link', ''), image=header.get('image', ''), tier=tier, **extra,
    )


def _names(value):
    return tuple(part.strip() for part in value.split(',') if part.strip())


def _parse_hero(name, header, kind):
    """The hero keys, validated: a hero that ships is a hero that renders."""
    if kind != 'new':
        raise ChangelogError(f'{name}: a hero must be kind: new (a fix is not news to sell)')
    if not header.get('link'):
        raise ChangelogError(f'{name}: a hero needs a link (the call to action)')
    if not header.get('cta_label'):
        raise ChangelogError(f'{name}: a hero needs a cta_label')
    art = header.get('art', '')
    if art and art not in ARTS:
        raise ChangelogError(f'{name}: art must be one of {ARTS}, got {art!r}')
    if not art and not header.get('image'):
        raise ChangelogError(f'{name}: a hero needs art or image (the plate)')
    show_if = _names(header.get('show_if', ''))
    note_if = header.get('note_if', '')
    for predicate in show_if + ((note_if,) if note_if else ()):
        if predicate not in PREDICATES:
            raise ChangelogError(
                f'{name}: unknown audience predicate {predicate!r}; '
                f'known: {sorted(PREDICATES)}')
    if note_if and not header.get('note'):
        raise ChangelogError(f'{name}: note_if without a note')
    chips = tuple(c.strip() for c in header.get('chips', '').split('|') if c.strip())
    return {
        'art': art, 'eyebrow': header.get('eyebrow', ''),
        'link_query': header.get('link_query', '').lstrip('?'),
        'cta_label': header['cta_label'], 'help': header.get('help', ''),
        'chips': chips, 'show_if': show_if, 'note_if': note_if,
        'note': header.get('note', ''),
    }


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


def heroes():
    """Hero entries, newest first."""
    return tuple(e for e in entries() if e.is_hero)


def latest_card(seen_id):
    """The newest unseen `card` entry -- what the small card shows. Heroes are
    skipped: a hero that is not pending (expired, out of audience) shows nothing."""
    for entry in unseen(seen_id):
        if not entry.is_hero:
            return entry
    return None


def hero_candidates(seen_id, today):
    """Unseen heroes still inside their lifetime, newest first. Pure: no audience
    yet, so callers can tell "nothing to evaluate" from "audience failed" without
    a query."""
    floor = today - datetime.timedelta(days=HERO_LIFETIME_DAYS)
    return tuple(e for e in unseen(seen_id) if e.is_hero and e.day >= floor)


def hero_for(seen_id, audience, today=None):
    """The hero pending for this creator: newest unseen, within lifetime, whose
    `show_if` all hold. `audience` is a `changelog_audience.Audience`; its
    predicates run only for candidates inside the window."""
    if today is None:
        from django.utils import timezone
        today = timezone.localdate()
    for entry in hero_candidates(seen_id, today):
        if audience.all(entry.show_if):
            return entry
    return None


def render_chips(entry, survey_names):
    """The example prompts with `{survey}` filled from the creator's own surveys,
    one name per chip, cycling; a chip that cannot be filled is dropped. Plain
    text -- the template escapes it."""
    names = [n for n in survey_names if n]
    out = []
    used = 0
    for chip in entry.chips:
        if CHIP_PLACEHOLDER not in chip:
            out.append(chip)
            continue
        if not names:
            continue
        out.append(chip.replace(CHIP_PLACEHOLDER, names[used % len(names)]))
        used += 1
    return out


def hero_spacing_violations(found=None):
    """Pairs of hero ids closer than `HERO_MIN_SPACING_DAYS` -- the budget. Empty
    when the directory keeps the rule; `ChangelogEntriesTest` asserts that."""
    found = sorted((e for e in (found if found is not None else entries()) if e.is_hero),
                   key=lambda e: e.id)
    bad = []
    for earlier, later in zip(found, found[1:]):
        if (later.day - earlier.day).days < HERO_MIN_SPACING_DAYS:
            bad.append((earlier.id, later.id))
    return bad


def clear_cache():
    """For tests that point the loader at a temporary directory."""
    _load.cache_clear()
