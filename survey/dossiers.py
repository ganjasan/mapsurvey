"""Parsing of the hand-written outreach dossiers under docs/marketing/user-outreach/.

The files were written by hand over months and are inconsistent by nature: only
29 of 125 carry an `Organization` header, and the same field appears as
`- **Organization**:`, `**Organization:**` and `## Organization` in different
files. So this module extracts the handful of labelled fields that do exist and
leaves the rest of the text alone -- the prose is preserved wholesale as a note,
which is where most of the value actually lives (creator-dossiers change, D3).

Read-only: nothing here writes to the source tree.
"""

import os
import re

# Header labels we recognise, mapped to CreatorProfile fields. `Location` feeds
# `country` -- the dossiers mix city and country freely and splitting them
# reliably is not worth a parser.
HEADER_FIELDS = (
    ('organization', ('organization', 'organisation', 'org')),
    ('role', ('role', 'position', 'title')),
    ('country', ('location', 'country', 'based in')),
    ('website', ('web', 'website', 'site', 'url')),
    ('linkedin_url', ('linkedin',)),
    ('how_found_us', ('how they found us', 'source', 'referrer')),
)

# `- **Organization**: value` / `**Role:** value` / `## Organization: value`
_HEADER_RE = re.compile(
    r'^\s*(?:[-*+]\s*)?(?:#{1,4}\s*)?\*{0,2}([A-Za-z][A-Za-z /]{2,30}?)\*{0,2}\s*[:：]\s*(.+?)\s*$'
)

_LINKEDIN_RE = re.compile(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/[^\s)>\]]+', re.I)
_URL_RE = re.compile(r'https?://[^\s)>\]]+')

# Correspondence filenames start with the date: 2026-04-28_initial-outreach.md
_DATE_PREFIX_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')

# Markdown decoration to strip off an extracted value.
_CLEAN_RE = re.compile(r'^[\s*_`]+|[\s*_`]+$')


def _clean(value):
    # `[[Northern University]]` -> `Northern University`
    value = re.sub(r'\[\[([^\]]+)\]\]', r'\1', value)
    # `[label](url)` -> `label`
    value = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', value)
    # Bold/italic markers survive mid-value (`**MAPS Studio** (domain …)`), not
    # just at the edges, so strip them everywhere rather than trimming the ends.
    value = value.replace('**', '').replace('__', '')
    return _CLEAN_RE.sub('', value)


def _is_placeholder(value):
    """True for values that record ignorance rather than a fact.

    The dossiers routinely write `Organization: Unknown — likely a university
    course instructor`. Storing that as an organisation would turn a guess into
    data; the sentence is preserved in the research note either way.
    """
    lowered = value.lower().strip(' .')
    if lowered in {'unknown', 'n/a', 'na', 'none', 'tbd', '—', '-', '?'}:
        return True
    return lowered.startswith(('unknown', 'not known', 'unclear', 'tbd'))


def parse_profile_fields(text, max_lines=40):
    """Extract labelled header fields from a dossier body.

    Only the top of the file is scanned: further down, lines like
    "Organization: ..." belong to quoted research rather than to this person.
    Unlabelled prose is never guessed at. Returns a dict of non-empty
    CreatorProfile fields.

    `Tier` is not among the recognised labels on purpose -- it duplicates, badly
    and stalely, what the funnel dashboard computes live (design D3).
    """
    found = {}
    for line in text.splitlines()[:max_lines]:
        match = _HEADER_RE.match(line)
        if not match:
            continue
        label = match.group(1).strip().lower()
        value = _clean(match.group(2))
        if not value or _is_placeholder(value):
            continue
        for field, labels in HEADER_FIELDS:
            if label in labels and field not in found:
                found[field] = value[:300 if field.endswith('url') else 200]
                break

    # A LinkedIn URL anywhere in the file beats a header that only names a person.
    if 'linkedin_url' not in found or not found['linkedin_url'].startswith('http'):
        link = _LINKEDIN_RE.search(text)
        if link:
            found['linkedin_url'] = link.group(0)[:300]
        else:
            found.pop('linkedin_url', None)

    if 'website' in found and not found['website'].startswith('http'):
        url = _URL_RE.search(found['website'])
        found['website'] = url.group(0)[:300] if url else ''
        if not found['website']:
            del found['website']

    return found


_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')


def parse_emails(text, max_lines=40):
    """Email addresses from the dossier header, in order of appearance.

    The directory name matches the account only 85 times out of 125: dossiers use
    `j_okafor` where the account is `j.okafor.2@example.edu`, `roseb` where it
    is `RoseB.`. The email in the header is the reliable join key, so the
    importer falls back to it (creator-dossiers change, D3).
    """
    found = []
    for line in text.splitlines()[:max_lines]:
        for match in _EMAIL_RE.finditer(line):
            address = match.group(0).lower().rstrip('.')
            if address not in found:
                found.append(address)
    return found


def normalised_names(dirname):
    """Plausible username spellings for a dossier directory name.

    Covers the observed drift: `sample_w266` vs `sample.w266`, `@handle123`
    written without the leading at-sign.
    """
    base = dirname.lower()
    variants = [base, base.replace('_', '.'), base.replace('.', '_'), '@' + base]
    return list(dict.fromkeys(variants))


def date_from_filename(name):
    """`2026-04-28_initial-outreach.md` -> `datetime.date(2026, 4, 28)`, else None."""
    import datetime

    match = _DATE_PREFIX_RE.match(os.path.basename(name))
    if not match:
        return None
    try:
        return datetime.date(*(int(g) for g in match.groups()))
    except ValueError:
        return None


def iter_dossiers(root):
    """Yield `(dirname, profile_path_or_None, [correspondence_paths])` per subdirectory.

    Sorted so a run is reproducible and its report is diffable.
    """
    if not os.path.isdir(root):
        return
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        profile = os.path.join(path, 'profile.md')
        if not os.path.exists(profile):
            # A few dossiers use another filename; take the first markdown file.
            candidates = sorted(
                f for f in os.listdir(path) if f.endswith('.md')
            )
            profile = os.path.join(path, candidates[0]) if candidates else None

        corr_dir = os.path.join(path, 'correspondence')
        correspondence = []
        if os.path.isdir(corr_dir):
            correspondence = [
                os.path.join(corr_dir, f)
                for f in sorted(os.listdir(corr_dir)) if f.endswith('.md')
            ]
        yield name, profile, correspondence
