"""Find a marker icon by meaning (change api-v2-structure, #412).

The server-side twin of the editor picker's search (`js/icon_picker.js`):
the same catalog (`marker_icons.catalog()`), the same haystack per language
-- the name without its prefix, the label, the English terms, plus the
language's own terms -- and the same rule: every whitespace token is a
substring of the language's haystack or the English one. The picker shows
matches in catalog order under the category the creator picked; a client
without a grid gets a ranked list instead: an exact name or label word
first, then a token that starts a word, then catalog order.
"""
import re
from functools import lru_cache

from . import marker_icons

SETS = ('maki', 'temaki', 'fa')
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_QUERY = 64
_FA_PREFIX = re.compile(r'^(fas|far|fab|fa) fa-')


def _set_of(value):
    return value.split(':', 1)[0] if ':' in value else 'fa'


@lru_cache(maxsize=1)
def _index():
    rows = []
    for position, icon in enumerate(marker_icons.catalog()['icons']):
        value = icon['v']
        if not marker_icons.is_drawable(value):
            continue
        name = _FA_PREFIX.sub('', value).split(':', 1)[-1]
        words = name.replace('-', ' ').replace('_', ' ')
        label = icon.get('l') or name
        terms = icon.get('t') or {}
        base = f" {words} {label.lower()} {terms.get('en', '')} "
        hay = {lang: (base if lang == 'en' else f"{base}{text} ") for lang, text in terms.items()}
        hay['en'] = base
        rows.append({
            'value': value, 'label': label, 'set': _set_of(value), 'categories': list(icon.get('c') or []),
            'position': position, 'hay': hay, 'exact': {words, *label.lower().split()},
        })
    return rows


def _rank(row, tokens, lang):
    hay = row['hay'].get(lang) or row['hay']['en']
    if any(t in row['exact'] or t == row['label'].lower() for t in tokens):
        tier = 0
    elif all(f' {t}' in hay or f' {t}' in row['hay']['en'] for t in tokens):
        tier = 1
    else:
        tier = 2
    return tier, row['position']


def search(query, *, lang='en', sets=None, limit=DEFAULT_LIMIT):
    """`[{value, label, set, categories}]` for `query`, best first. An empty
    query lists the catalog in its own order."""
    lang = (lang or 'en').split('-')[0].lower()
    tokens = (query or '').strip().lower()[:MAX_QUERY].split()
    wanted = set(sets) if sets else None
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    hits = []
    for row in _index():
        if wanted and row['set'] not in wanted:
            continue
        hay = row['hay'].get(lang) or row['hay']['en']
        en = row['hay']['en']
        if all(t in hay or t in en for t in tokens):
            hits.append(row)
    if tokens:
        hits.sort(key=lambda row: _rank(row, tokens, lang))
    return [{'value': r['value'], 'label': r['label'], 'set': r['set'], 'categories': r['categories']}
            for r in hits[:limit]]


def ui_language(user):
    """The creator's chosen interface language, else English."""
    from .models import CreatorPreferences
    prefs = CreatorPreferences.objects.filter(user=user).only('ui_language').first()
    return (prefs.ui_language if prefs else '') or 'en'


def report_miss(user, query, lang, *, surface):
    """`icon_search_miss`, the event the editor picker sends, so a "creators
    type X and find nothing" report covers agents too; the fix is a row in
    `scripts/icon_terms/<lang>/`."""
    from . import product_events as pe
    pe.emit('icon_search_miss', getattr(user, 'pk', None),
            {'query': (query or '').strip()[:MAX_QUERY], 'lang': lang, 'surface': surface})
