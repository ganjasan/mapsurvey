"""Sites (change landing-core, #576; epic #348).

A `Site` is a workspace's public page for an engagement at /p/<slug>/. Its content is an
ordered list of `SiteBlock`s of a closed set of kinds; every write of a block's data goes
through `clean_block`, so what the builder saves is exactly what the templates can draw.
A new kind (documents, map, results, events — #577–#579) is one entry in `BLOCK_KINDS`, its
cleaner here and its two templates (`sites/blocks/<kind>.html` for the page,
`sites/forms/<kind>.html` for the builder) — never a column.

Surveys are linked many-to-many through `SiteSurvey` (canonical surveys of the site's
own workspace); a survey card reads the survey's state at render time (`survey_card`).
"""
import re

from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .html_sanitize import coerce_creator_html
from .redirects import is_valid_redirect

SLUG_MIN = 3
SLUG_MAX = 64
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
RESERVED_SLUGS = frozenset({'new', 'edit', 'report', 'admin', 'preview', 'api', 'static', 'media'})

TITLE_MAX = 120
SUMMARY_MAX = 300
RICH_TEXT_MAX = 20000
FAQ_ANSWER_MAX = 4000
FAQ_MAX_ITEMS = 30
TIMELINE_MAX_ITEMS = 12
IMAGE_MAX_BYTES = 5 * 1024 * 1024

ACTING_ROLES = ('owner', 'admin', 'editor')
FEATURE = 'sites'


class BlockInvalid(Exception):
    """`errors` is {field: message}."""

    def __init__(self, errors):
        super().__init__(errors)
        self.errors = errors


# ─── block kinds ──────────────────────────────────────────────────────────────

# key → (label, icon, group) for the "Add block" picker, in picker order.
BLOCK_KINDS = {
    'heading': (gettext_lazy('Heading'), 'fas fa-heading', 'content'),
    'text': (gettext_lazy('Text'), 'fas fa-align-left', 'content'),
    'faq': (gettext_lazy('FAQ'), 'far fa-question-circle', 'content'),
    'timeline': (gettext_lazy('Timeline'), 'fas fa-stream', 'content'),
    'image': (gettext_lazy('Image'), 'far fa-image', 'media'),
    'video': (gettext_lazy('Video'), 'fab fa-youtube', 'media'),
    'map': (gettext_lazy('Map'), 'fas fa-draw-polygon', 'media'),
    'gallery': (gettext_lazy('Gallery'), 'far fa-images', 'media'),
    'compare': (gettext_lazy('Before and after'), 'fas fa-columns', 'media'),
    'results': (gettext_lazy('Results'), 'fas fa-chart-bar', 'media'),
    'documents': (gettext_lazy('Documents'), 'far fa-file-pdf', 'participation'),
    'event': (gettext_lazy('Event'), 'far fa-calendar-check', 'participation'),
    'survey': (gettext_lazy('Survey card'), 'fas fa-map-marked-alt', 'participation'),
    'button': (gettext_lazy('Button'), 'fas fa-link', 'participation'),
    'contacts': (gettext_lazy('Contacts'), 'far fa-address-card', 'participation'),
    'updates': (gettext_lazy('Updates'), 'far fa-newspaper', 'content'),
}

PICKER_GROUPS = (
    ('content', gettext_lazy('Text-based content')),
    ('media', gettext_lazy('Media')),
    ('participation', gettext_lazy('Participation and links')),
)


def picker():
    """[(group label, [(kind, label, icon)])] for the Add block dialog."""
    out = []
    for key, label in PICKER_GROUPS:
        out.append((label, [(k, v[0], v[1]) for k, v in BLOCK_KINDS.items() if v[2] == key]))
    return out


# The block library of the canvas builder (change landing-builder-redesign): groups named by what
# the creator is doing, each tile with one line of what the block is for.
LIBRARY = (
    (gettext_lazy('Tell the story'), (
        ('heading', gettext_lazy('A section title on its own, in one of three sizes')),
        ('text', gettext_lazy('Purpose, background, what happens next')),
        ('timeline', gettext_lazy('Phases with dates; mark the one you are in')),
        ('faq', gettext_lazy('Questions residents keep asking')),
        ('image', gettext_lazy('A photo or a plan drawing with a caption')),
        ('gallery', gettext_lazy('Boards, renderings or site photos, opened large on a tap')),
        ('compare', gettext_lazy('Today and the proposal, side by side with a slider')),
        ('video', gettext_lazy('YouTube or Vimeo')),
        ('map', gettext_lazy('The project area from a GeoJSON file')),
    )),
    (gettext_lazy('Take part'), (
        ('survey', gettext_lazy('One of your surveys; follows its status')),
        ('event', gettext_lazy('Open house or walk, with registration')),
        ('button', gettext_lazy('A link to anything else')),
        ('contacts', gettext_lazy('Who runs the project and how to reach them')),
    )),
    (gettext_lazy('Show the work'), (
        ('results', gettext_lazy("A chart or a map from a survey's answers")),
        ('documents', gettext_lazy('Summaries, boards, the draft plan')),
        ('updates', gettext_lazy('News and “You said, we did”, newest first')),
    )),
)


def library():
    """[(group label, [(kind, label, icon, description)])]; every kind appears exactly once."""
    return [(label, [(k, BLOCK_KINDS[k][0], BLOCK_KINDS[k][1], desc) for k, desc in tiles])
            for label, tiles in LIBRARY]


def _plain(value, cap):
    return ' '.join(str(value or '').split())[:cap]


def _rich(value, cap):
    html = coerce_creator_html(str(value or ''))
    return html[:cap] if html else ''


# Kinds that may break out of the site's column to the page edge (change site-width).
WIDE_KINDS = ('image', 'video', 'map', 'gallery', 'compare')
GALLERY_MAX = 12
GALLERY_COLUMNS = ('2', '3', '4')
SITE_WIDTHS = ('narrow', 'standard', 'wide')


def _wide(raw):
    return raw.get('wide') in ('1', 'on', True)


def _is_empty_html(html):
    return not re.sub(r'<[^>]+>|&nbsp;|\s', '', html or '')


# A heading block's sizes (change site-heading-block): large and medium are <h2>, small is <h3>;
# the site's title is the page's only <h1>.
HEADING_SIZES = ('l', 'm', 's')


def _clean_heading(raw, errors):
    # The words are the block's title (edited on the canvas, capped by clean_title).
    size = raw.get('size') if raw.get('size') in HEADING_SIZES else 'm'
    return {'size': size}


def _demote_h1(html):
    """The site title is the page's only <h1>: a heading written in a text block is at most <h2>."""
    return re.sub(r'<(/?)h1\b', r'<\1h2', html or '')


def _clean_text(raw, errors):
    body = _demote_h1(_rich(raw.get('body'), RICH_TEXT_MAX))
    if _is_empty_html(body):
        errors['body'] = _('Write some text.')
    return {'body': body}


def _clean_image(raw, errors):
    return {'alt': _plain(raw.get('alt'), 200), 'caption': _plain(raw.get('caption'), 300), 'wide': _wide(raw)}


def _clean_button(raw, errors):
    label = _plain(raw.get('label'), 60)
    url = str(raw.get('url') or '').strip()
    style = raw.get('style') if raw.get('style') in ('primary', 'secondary') else 'primary'
    if not label:
        errors['label'] = _('Give the button a label.')
    if not (url.lower().startswith(('http://', 'https://')) and is_valid_redirect(url)):
        errors['url'] = _('Enter a full web address that starts with https://')
    return {'label': label, 'url': url, 'style': style}


def _clean_video(raw, errors):
    from .layer_assets import AssetRejected, normalize_embed_url
    url = str(raw.get('url') or '').strip()
    embed = ''
    try:
        embed = normalize_embed_url(url)
    except AssetRejected as exc:
        errors['url'] = str(exc)
    return {'url': url[:500], 'embed': embed, 'caption': _plain(raw.get('caption'), 300), 'wide': _wide(raw)}


def _items(raw):
    items = raw.get('items')
    return items if isinstance(items, list) else []


def _clean_faq(raw, errors):
    items = []
    for item in _items(raw)[:FAQ_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        q = _plain(item.get('q'), 200)
        a = _rich(item.get('a'), FAQ_ANSWER_MAX)
        if q or not _is_empty_html(a):
            items.append({'q': q, 'a': '' if _is_empty_html(a) else a})
    if not items:
        errors['items'] = _('Add at least one question.')
    elif any(not i['q'] for i in items):
        errors['items'] = _('Every answer needs its question.')
    return {'items': items}


def _clean_timeline(raw, errors):
    items = []
    for item in _items(raw)[:TIMELINE_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        title = _plain(item.get('title'), 120)
        when = _plain(item.get('when'), 60)
        body = _plain(item.get('body'), 600)
        if title or when or body:
            items.append({'title': title, 'when': when, 'body': body})
    if not items:
        errors['items'] = _('Add at least one phase.')
    elif any(not i['title'] for i in items):
        errors['items'] = _('Every phase needs a title.')
    current = raw.get('current')
    try:
        current = int(current) if current not in (None, '') else None
    except (TypeError, ValueError):
        current = None
    if current is not None and not 0 <= current < len(items):
        current = None
    return {'items': items, 'current': current}


CONTACTS_MAX = 6


def _clean_contacts(raw, errors):
    """The project team (change site-contacts-block): up to six people, each name / role / e-mail /
    phone, plus an address and opening hours. A row without a name is kept and not drawn (it is being
    typed on the canvas); a malformed e-mail is refused."""
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    people, bad = [], []
    rows = raw.get('people')
    for p in (rows if isinstance(rows, list) else [])[:CONTACTS_MAX]:
        if not isinstance(p, dict):
            continue
        person = {'name': _plain(p.get('name'), 120), 'role': _plain(p.get('role'), 120),
                  'email': _plain(p.get('email'), 254), 'phone': _plain(p.get('phone'), 40)}
        if not any(person.values()):
            continue
        if person['email']:
            try:
                validate_email(person['email'])
            except ValidationError:
                bad.append(person['email'])
        people.append(person)
    if bad:
        errors['people'] = _('“%(email)s” is not an e-mail address.') % {'email': bad[0]}
    return {'people': people, 'address': _plain_lines(raw.get('address'), 300),
            'hours': _plain(raw.get('hours'), 200)}


def _plain_lines(value, cap):
    lines = [' '.join(line.split()) for line in str(value or '').splitlines()]
    return '\n'.join(line for line in lines if line)[:cap]


def _clean_gallery(raw, errors):
    # The pictures are SiteFile rows (change site-gallery-compare), like a documents block's files.
    columns = str(raw.get('columns') or '3')
    return {'columns': int(columns if columns in GALLERY_COLUMNS else '3'), 'wide': _wide(raw)}


def _clean_compare(raw, errors):
    # Two SiteFile rows: order 0 is "before", order 1 is "after".
    return {'before_label': _plain(raw.get('before_label'), 40), 'after_label': _plain(raw.get('after_label'), 40),
            'wide': _wide(raw)}


def _clean_documents(raw, errors):
    # The files are SiteFile rows (change landing-documents-map); the block keeps no data.
    return {}


DEFAULT_MAP_COLOR = '#2f6fb0'
_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def _clean_map(raw, errors, org=None):
    from . import basemaps
    color = str(raw.get('color') or '').strip()
    color = color.lower() if _HEX.match(color) else DEFAULT_MAP_COLOR
    basemap = str(raw.get('basemap') or '').strip()
    if not basemap or (org is not None and basemaps.resolve(basemap, org) is None):
        basemap = 'streets'
    area = raw.get('area')
    if not (isinstance(area, dict) and area.get('features')):
        errors['area'] = _('Upload a GeoJSON file with the project area.')
        area = None
    return {'area': area, 'color': color, 'basemap': basemap,
            'caption': _plain(raw.get('caption'), 300), 'wide': _wide(raw)}


CHART_VIZ = ('auto', 'bar', 'pie', 'donut', 'table')
MAP_VIZ = ('auto', 'heatmap', 'cluster')


def _clean_results(raw, errors, org=None):
    """`question_code` and `kind_of` (chart | map | objects) are set by the view after it found
    the question; the cleaner only bounds the options against that kind."""
    from . import basemaps
    code = _plain(raw.get('question_code'), 100)
    result_kind = raw.get('result_kind')
    if not code or result_kind not in ('chart', 'map', 'objects'):
        errors['question'] = _('Pick a question whose answers can be shown as a chart or a map.')
    allowed = MAP_VIZ if result_kind == 'map' else CHART_VIZ if result_kind == 'chart' else ('auto',)
    viz = raw.get('viz') if raw.get('viz') in allowed else 'auto'
    basemap = str(raw.get('basemap') or '').strip()
    if not basemap or (org is not None and basemaps.resolve(basemap, org) is None):
        basemap = 'streets'
    return {'question_code': code, 'result_kind': result_kind or '', 'viz': viz,
            'basemap': basemap if result_kind == 'map' else '',
            'caption': _plain(raw.get('caption'), 300)}


_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_TIME = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def _clean_event(raw, errors):
    from zoneinfo import available_timezones
    date = str(raw.get('date') or '').strip()
    start = str(raw.get('start') or '').strip()
    end = str(raw.get('end') or '').strip()
    tz = str(raw.get('tz') or 'UTC').strip()
    if not _DATE.match(date):
        errors['date'] = _('Pick the date of the event.')
    if not _TIME.match(start):
        errors['start'] = _('Enter the start time.')
    if end and (not _TIME.match(end) or (_TIME.match(start) and end <= start)):
        errors['end'] = _('The end time must be after the start.')
    if tz != 'UTC' and tz not in available_timezones():
        errors['tz'] = _('Pick a time zone from the list, e.g. Europe/Berlin.')
    place_url = str(raw.get('place_url') or '').strip()
    if place_url and not (place_url.lower().startswith(('http://', 'https://')) and is_valid_redirect(place_url)):
        errors['place_url'] = _('Enter a full web address that starts with https://')
    capacity = str(raw.get('capacity') or '').strip()
    if capacity:
        try:
            capacity = int(capacity)
            if not 1 <= capacity <= 10000:
                raise ValueError
        except ValueError:
            errors['capacity'] = _('Seats must be a number from 1 to 10000, or empty for no limit.')
            capacity = None
    else:
        capacity = None
    return {'date': date, 'start': start, 'end': end, 'tz': tz,
            'place': _plain(raw.get('place'), 200), 'place_url': place_url[:250],
            'description': ' '.join(str(raw.get('description') or '').split(' '))[:1000].strip(),
            'capacity': capacity, 'open': raw.get('open') in (True, '1', 'on', 'true')}


def _clean_survey(raw, errors):
    return {'button_label': _plain(raw.get('button_label'), 40),
            'description': _plain(raw.get('description'), 300)}


# ─── updates (change site-updates, #629) ──────────────────────────────────────

UPDATE_COUNTS = ('3', '5', '10', '0')  # 0 = all
UPDATE_KIND_FILTERS = ('', 'news', 'decision')
UPDATE_TITLE_MAX = 160
UPDATE_SAID_MAX = 2000
UPDATE_STATUSES = ('included', 'partly', 'not')


def _clean_updates(raw, errors):
    count = str(raw.get('count') or '3')
    kinds = str(raw.get('kinds') or '')
    return {'count': int(count) if count in UPDATE_COUNTS else 3,
            'kinds': kinds if kinds in UPDATE_KIND_FILTERS else ''}


def feed(site, *, kinds='', drafts=False):
    """The site's updates, newest first: published only unless `drafts`; one kind when `kinds`."""
    qs = site.updates.select_related('site_survey__survey')
    if not drafts:
        qs = qs.filter(is_published=True)
    if kinds:
        qs = qs.filter(kind=kinds)
    return qs.order_by('-date', '-id')


def decorate_updates(site, updates, *, lang='', review=''):
    """Give each update what its card links to: `url` (its own page), `survey_label`/`survey_url` (the
    linked survey, opened while it runs, its results once closed)."""
    for u in updates:
        u.url = updates_url(site, u, lang=lang, review=review)
        link = u.site_survey
        u.survey_label, u.survey_url = '', ''
        if link is not None:
            card = survey_card(link.survey)
            if card['state'] != CARD_HIDDEN:
                u.survey_label = link.survey.name
                u.survey_url = card['url'] or card['results_url']
    return updates


def updates_card(block, drafts=False):
    """What an `updates` block draws: {'updates': [...], 'more': bool}, or None when it has nothing."""
    data = block.data if isinstance(block.data, dict) else {}
    rows = feed(block.site, kinds=data.get('kinds') or '', drafts=drafts)
    count = data.get('count', 3)
    if count:
        items = list(rows[:count + 1])
        more = len(items) > count
        items = items[:count]
    else:
        items, more = list(rows), False
    if not items:
        return None
    return {'updates': items, 'more': more}


_CLEANERS = {
    'heading': _clean_heading,
    'text': _clean_text,
    'image': _clean_image,
    'button': _clean_button,
    'video': _clean_video,
    'faq': _clean_faq,
    'timeline': _clean_timeline,
    'survey': _clean_survey,
    'documents': _clean_documents,
    'map': _clean_map,
    'results': _clean_results,
    'event': _clean_event,
    'contacts': _clean_contacts,
    'gallery': _clean_gallery,
    'compare': _clean_compare,
    'updates': _clean_updates,
}


def clean_block(kind, raw, org=None, creating=False):
    """(data, errors) for a block of `kind` from the posted `raw` dict. `data` carries only
    the kind's keys, trimmed and capped; rich text has passed `coerce_creator_html`. `org`
    lets the map cleaner check its base map against the workspace's. `creating` (change
    landing-builder-redesign) is the library adding an EMPTY block: the "required" errors are
    dropped so the block exists on the canvas; `is_complete` keeps it off the public page."""
    if kind not in _CLEANERS:
        return {}, {'kind': _('Unknown block type.')}
    errors = {}
    raw = raw if isinstance(raw, dict) else {}
    if kind == 'map':
        data = _clean_map(raw, errors, org=org)
    elif kind == 'results':
        data = _clean_results(raw, errors, org=org)
    else:
        data = _CLEANERS[kind](raw, errors)
    if creating:
        errors.clear()
    return data, errors


def is_complete(block):
    """Whether the public page draws the block (change landing-builder-redesign): a block
    the library just added, or one the creator emptied, stays in the builder only."""
    data = block.data if isinstance(block.data, dict) else {}
    kind = block.kind
    if kind == 'heading':
        return bool(block.title)
    if kind == 'gallery':
        return block.files.exists()
    if kind == 'compare':
        return set(block.files.values_list('order', flat=True)) >= {0, 1}
    if kind == 'contacts':
        return any(p.get('name') for p in data.get('people') or ()) or bool(data.get('address'))
    if kind == 'text':
        return not _is_empty_html(data.get('body'))
    if kind == 'image':
        return bool(block.image)
    if kind == 'button':
        return bool(data.get('label')) and bool(data.get('url'))
    if kind == 'video':
        return bool(data.get('embed'))
    if kind in ('faq', 'timeline'):
        # A row still missing its question / title (saved while the creator types on the
        # canvas) is not drawn; the block is drawn while one row is whole.
        key = 'q' if kind == 'faq' else 'title'
        return any(isinstance(i, dict) and i.get(key) for i in data.get('items') or ())
    if kind == 'documents':
        return bool(block.files.all())
    if kind == 'map':
        return bool(data.get('area'))
    if kind == 'results':
        return bool(data.get('question_code')) and block.site_survey_id is not None
    if kind == 'event':
        from . import site_events
        return bool(data.get('start')) and site_events.starts_at(data) is not None
    if kind == 'survey':
        return block.site_survey_id is not None
    return True


def clean_title(value):
    return _plain(value, TITLE_MAX)


_IMAGE_FORMATS = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}


def check_image(upload):
    """An error message for an uploaded picture, or ''. The BYTES decide, never the browser's
    content type or the file name: Pillow must recognise a JPEG, PNG, WebP or GIF, and the
    upload is renamed to that format's extension, so the stored key (and the content type the
    public media host serves) can only be an image — a renamed HTML or SVG never gets there."""
    if upload is None:
        return ''
    if upload.size > IMAGE_MAX_BYTES:
        return _('The picture is larger than 5 MB.')
    from PIL import Image, UnidentifiedImageError
    try:
        upload.seek(0)
        with Image.open(upload) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        fmt = None
    finally:
        upload.seek(0)
    if fmt not in _IMAGE_FORMATS:
        return _('Upload a JPEG, PNG, WebP or GIF picture.')
    upload.name = f'image.{_IMAGE_FORMATS[fmt]}'
    return ''


# ─── documents (change landing-documents-map) ─────────────────────────────────

DOCUMENT_MAX_BYTES = 25 * 1024 * 1024
DOCUMENTS_MAX = 20
_PDF, _ZIP, _OLE, _TEXT = 'pdf', 'zip', 'ole', 'text'
DOCUMENT_FAMILIES = {
    'pdf': _PDF, 'docx': _ZIP, 'xlsx': _ZIP, 'pptx': _ZIP, 'odt': _ZIP, 'ods': _ZIP, 'odp': _ZIP,
    'doc': _OLE, 'xls': _OLE, 'ppt': _OLE, 'csv': _TEXT, 'txt': _TEXT,
}
_MAGIC = {_PDF: (b'%PDF-',), _ZIP: (b'PK\x03\x04',), _OLE: (b'\xd0\xcf\x11\xe0',)}
_MARKUP = re.compile(rb'<\s*(html|script|svg|iframe|body|head|!doctype)', re.I)


def check_document(upload):
    """An error message for an uploaded document, or ''. Extension AND first bytes: a renamed
    HTML or SVG must never reach the public media host, where it would run as a page."""
    name = getattr(upload, 'name', '') or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    family = DOCUMENT_FAMILIES.get(ext)
    if family is None:
        return _('“%(name)s”: upload a PDF, an office document, CSV or plain text.') % {'name': name}
    if upload.size > DOCUMENT_MAX_BYTES:
        return _('“%(name)s” is larger than 25 MB.') % {'name': name}
    upload.seek(0)
    head = upload.read(4096)
    upload.seek(0)
    if family == _TEXT:
        try:
            head.decode('utf-8')
        except UnicodeDecodeError:
            # A cut multi-byte character at the 4 KB edge is fine; garbage is not.
            try:
                head[:-3].decode('utf-8')
            except UnicodeDecodeError:
                return _('“%(name)s” is not a UTF-8 text file.') % {'name': name}
        if _MARKUP.search(head):
            return _('“%(name)s” looks like a web page, not a document.') % {'name': name}
        return ''
    if not any(head.startswith(m) for m in _MAGIC[family]):
        return _('“%(name)s” is not the kind of file its name says.') % {'name': name}
    return ''


def document_title(filename):
    base = filename.rsplit('/', 1)[-1]
    base = base.rsplit('.', 1)[0] if '.' in base else base
    return _plain(base.replace('_', ' '), 200) or _('Document')


TYPE_LABELS = {'pdf': 'PDF', 'docx': 'Word', 'doc': 'Word', 'odt': 'Text document',
               'xlsx': 'Excel', 'xls': 'Excel', 'ods': 'Spreadsheet', 'pptx': 'PowerPoint',
               'ppt': 'PowerPoint', 'odp': 'Presentation', 'csv': 'CSV', 'txt': 'Text'}


# ─── map area (change landing-documents-map) ──────────────────────────────────

GEOJSON_MAX_BYTES = 1024 * 1024
GEOJSON_MAX_FEATURES = 500
GEOMETRY_TYPES = ('Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon')


def _round(coords):
    if isinstance(coords, (int, float)):
        return round(float(coords), 6)
    return [_round(c) for c in coords]


def parse_geojson(upload):
    """(FeatureCollection, '') from an uploaded GeoJSON file, or (None, error). Keeps only each
    feature's geometry and a name; coordinates rounded to 6 decimals (~10 cm)."""
    import json

    from django.contrib.gis.geos import GEOSException, GEOSGeometry

    if upload.size > GEOJSON_MAX_BYTES:
        return None, _('The GeoJSON file is larger than 1 MB.')
    try:
        doc = json.loads(upload.read().decode('utf-8-sig'))
    except (ValueError, UnicodeDecodeError):
        return None, _('This is not a GeoJSON file.')
    if not isinstance(doc, dict):
        return None, _('This is not a GeoJSON file.')
    if doc.get('type') == 'FeatureCollection':
        features = doc.get('features') if isinstance(doc.get('features'), list) else []
    elif doc.get('type') == 'Feature':
        features = [doc]
    else:
        features = [{'type': 'Feature', 'geometry': doc, 'properties': {}}]
    if len(features) > GEOJSON_MAX_FEATURES:
        return None, _('The file has more than 500 features.')
    out = []
    for feature in features:
        geometry = feature.get('geometry') if isinstance(feature, dict) else None
        if not isinstance(geometry, dict) or geometry.get('type') not in GEOMETRY_TYPES:
            continue
        try:
            geos = GEOSGeometry(json.dumps(geometry))
        except (GEOSException, ValueError, TypeError):
            return None, _('A shape in the file is broken.')
        x0, y0, x1, y1 = geos.extent
        if not (-180 <= x0 <= x1 <= 180 and -90 <= y0 <= y1 <= 90):
            return None, _('Coordinates must be longitude and latitude (WGS84).')
        if geometry['type'] in ('Polygon', 'MultiPolygon') and not geos.valid:
            return None, _('A polygon in the file crosses itself.')
        props = feature.get('properties') if isinstance(feature.get('properties'), dict) else {}
        name = next((props[k] for k in ('name', 'title', 'Name') if isinstance(props.get(k), str)), '')
        out.append({'type': 'Feature',
                    'geometry': {'type': geometry['type'], 'coordinates': _round(geometry['coordinates'])},
                    'properties': {'name': _plain(name, 120)} if name.strip() else {}})
    if not out:
        return None, _('The file has no points, lines or areas.')
    return {'type': 'FeatureCollection', 'features': out}, ''


# ─── slugs ────────────────────────────────────────────────────────────────────

def slug_error(slug, site=None):
    """A field error for `slug`, or ''."""
    from .models import Site
    if not (SLUG_MIN <= len(slug) <= SLUG_MAX) or not SLUG_RE.match(slug):
        return _('Use 3–64 lowercase letters, digits and dashes.')
    if slug in RESERVED_SLUGS:
        return _('This address is reserved. Pick another.')
    taken = Site.objects.filter(slug=slug)
    if site is not None and site.pk:
        taken = taken.exclude(pk=site.pk)
    if taken.exists():
        return _('Another site already uses this address.')
    return ''


PLACEHOLDER_SLUG = 'untitled'
_PLACEHOLDER_RE = re.compile(r'^untitled(-\d+)?$')


def has_placeholder_slug(site):
    """A page created with "New site" and never published keeps an address made from nothing;
    the first real title gives it one."""
    return not site.is_published and site.published_at is None and bool(_PLACEHOLDER_RE.match(site.slug))


def unique_slug(title):
    from .models import Site
    base = slugify(title)[:SLUG_MAX - 4].strip('-') or 'site'
    if len(base) < SLUG_MIN or base in RESERVED_SLUGS:
        base = f'{base}-page'.strip('-')
    slug, n = base, 2
    while Site.objects.filter(slug=slug).exists():
        slug = f'{base}-{n}'
        n += 1
    return slug


# ─── pages (change site-pages, #628) ──────────────────────────────────────────

PAGES_MAX = 12
PAGE_TITLE_MAX = 60
# Segments under /p/<slug>/ that are routes of their own, now or in wave C (updates #629, embed #631).
RESERVED_PAGE_SLUGS = frozenset({'report', 'events', 'updates', 'embed', 'review', 'feed', 'new', 'edit',
                                 'admin', 'api', 'static', 'media'})


def home_page(site):
    """The site's home page, created on first need (new sites, and blocks saved with `site=` only)."""
    from django.utils import translation

    from .models import SitePage
    page = SitePage.objects.filter(site=site, is_home=True).first()
    if page is None:
        with translation.override(site.language or 'en'):
            title = _('Home')
        page, _created = SitePage.objects.get_or_create(site=site, is_home=True,
                                                        defaults={'title': title, 'order': 0})
    return page


def pages_for(site):
    """The site's pages in order, home first (created when missing)."""
    pages = list(site.pages.order_by('-is_home', 'order', 'id'))
    if not pages or not pages[0].is_home:
        home_page(site)
        pages = list(site.pages.order_by('-is_home', 'order', 'id'))
    return pages


def page_for(site, slug):
    """The page `slug` names ('' = home), or None."""
    if not slug:
        return home_page(site)
    return site.pages.filter(slug=slug, is_home=False).first()


def page_slug_error(slug, page):
    """A field error for a page address, or ''."""
    from .models import SitePage
    if not (1 <= len(slug) <= SLUG_MAX) or not SLUG_RE.match(slug):
        return _('Use lowercase letters, digits and dashes.')
    if slug in RESERVED_PAGE_SLUGS:
        return _('This address is reserved. Pick another.')
    if SitePage.objects.filter(site_id=page.site_id, slug=slug, is_home=False).exclude(pk=page.pk).exists():
        return _('Another page of this site already uses this address.')
    return ''


def unique_page_slug(site, title, exclude=None):
    from .models import SitePage
    base = slugify(title)[:SLUG_MAX - 4].strip('-') or 'page'
    if base in RESERVED_PAGE_SLUGS:
        base = f'{base}-page'
    taken = SitePage.objects.filter(site=site, is_home=False)
    if exclude is not None:
        taken = taken.exclude(pk=exclude.pk)
    taken = set(taken.values_list('slug', flat=True))
    slug, n = base, 2
    while slug in taken:
        slug = f'{base}-{n}'
        n += 1
    return slug


def page_url(site, page, *, lang='', review='', absolute=False):
    """The address of `page`, keeping a non-primary language and an open review link."""
    from urllib.parse import urlencode

    from django.urls import reverse
    if page is None or page.is_home:
        url = reverse('site_public', args=[site.slug])
    else:
        url = reverse('site_page_public', args=[site.slug, page.slug])
    query = {}
    if lang and lang != site.language:
        query['lang'] = lang
    if review:
        query['review'] = review
    if query:
        url += '?' + urlencode(query)
    if absolute:
        from .mail import absolute_url
        url = absolute_url(url)
    return url


def updates_url(site, update=None, *, lang='', review=''):
    """The feed's address, or one update's, keeping a non-primary language and a review link."""
    from urllib.parse import urlencode

    from django.urls import reverse
    url = (reverse('site_update_public', args=[site.slug, update.pk]) if update is not None
           else reverse('site_updates_public', args=[site.slug]))
    query = {k: v for k, v in (('lang', lang if lang and lang != site.language else ''), ('review', review)) if v}
    return url + ('?' + urlencode(query) if query else '')


def menu(pages, page, blocks):
    """What the public menu shows: {'pages': [(page, current)] when two or more pages are in the
    menu, else [], 'anchors': [(anchor, title)] of the current page's titled blocks}."""
    listed = [p for p in pages if p.is_home or p.in_menu]
    return {
        'pages': [(p, p.pk == page.pk) for p in listed] if len(listed) > 1 else [],
        'anchors': [(b.anchor, b.title) for b, _card in blocks if b.title and b.in_menu],
    }


# ─── accessibility checks (change site-a11y-lint) ─────────────────────────────

# Link texts that say nothing out of context (WCAG 2.4.4). Lower-case, compared after trimming.
VAGUE_LINK_TEXTS = frozenset({'here', 'click here', 'this link', 'link', 'more', 'read more', 'this'})
_ANCHOR = re.compile(r'<a\b[^>]*>(.*?)</a>', re.S | re.I)


def _vague(text):
    return ' '.join(re.sub(r'<[^>]+>', '', text or '').split()).lower().strip('.:!') in VAGUE_LINK_TEXTS


def a11y_issues(site, blocks):
    """({block pk: [message]}, [site-level message]) — what a screen-reader or keyboard user would
    trip over. Shown in the builder, never blocking publish."""
    per_block, site_level = {}, []
    if site.cover and not site.cover_alt:
        site_level.append(_('The cover picture has no description for screen readers.'))
    seen_section_heading = False
    for b in blocks:
        data = b.data if isinstance(b.data, dict) else {}
        found = []
        if b.kind == 'image' and b.image and not data.get('alt'):
            found.append(_('The picture has no description for screen readers.'))
        if b.kind == 'gallery' and b.files.filter(title='').exists():
            found.append(_('Some pictures have no caption, which is what screen readers read out.'))
        if b.kind == 'heading' and b.title:
            if data.get('size') == 's' and not seen_section_heading:
                found.append(_('A small heading comes before any large or medium one: screen readers announce '
                               'it as a subsection of nothing. Make it medium, or add a heading above.'))
            elif data.get('size') != 's':
                seen_section_heading = True
        elif b.title:
            seen_section_heading = True
        if b.kind == 'text' and any(_vague(m) for m in _ANCHOR.findall(data.get('body') or '')):
            found.append(_('A link says only “here” or “more”. Name where it leads, e.g. “the draft plan (PDF)”.'))
        if b.kind == 'button' and _vague(data.get('label')):
            found.append(_('The button says only “here” or “more”. Name where it leads.'))
        if found:
            per_block[b.pk] = found
    return per_block, site_level


REVIEW_LINK_DAYS = 14


def _review_signer(site):
    from django.core.signing import TimestampSigner
    return TimestampSigner(salt=f'site-review:{site.pk}:{site.review_salt}')


def review_token(site):
    """A link token that opens the draft read-only for someone without an account (change
    site-review-link): signed with the site's review salt, valid REVIEW_LINK_DAYS."""
    return _review_signer(site).sign(str(site.pk))


def review_token_ok(site, token):
    from django.core.signing import BadSignature
    if not token:
        return False
    try:
        return _review_signer(site).unsign(token, max_age=REVIEW_LINK_DAYS * 86400) == str(site.pk)
    except BadSignature:  # also SignatureExpired
        return False


def rotate_review_salt(site):
    import secrets
    site.review_salt = secrets.token_hex(8)
    site.save(update_fields=['review_salt', 'updated_at'])


def duplicate_site(site, user, title):
    """A new unpublished site that starts as a copy of `site` (change site-duplicate): its settings,
    survey links, pages, blocks on their pages and their files — the stored objects are shared, as
    when a block is duplicated — but never event registrations. Survey cards and results blocks point at the
    copy's own links. Wave B moves this into the sites service."""
    from django.db import transaction
    from .models import Site, SiteBlock, SiteFile, SitePage, SiteSurvey
    with transaction.atomic():
        copy = Site.objects.create(
            organization=site.organization, title=title, summary=site.summary, created_by=user,
            slug=unique_slug(title), language=site.language, width=site.width,
            visibility=site.visibility, cover=site.cover.name if site.cover else None,
            cover_alt=site.cover_alt, languages=list(site.languages or []),
            translations=dict(site.translations or {}), translation_sources=dict(site.translation_sources or {}))
        links, remap, files_remap, pages = {}, {}, {}, {}
        for link in site.survey_links.order_by('order', 'id'):
            links[link.pk] = SiteSurvey.objects.create(site=copy, survey=link.survey, order=link.order)
        # Pages (change site-pages): same titles, addresses, menu flags and translations, home stays home.
        page_remap = {}
        for page in pages_for(site):
            pages[page.pk] = SitePage.objects.create(
                site=copy, title=page.title, slug=page.slug, order=page.order, in_menu=page.in_menu,
                is_home=page.is_home, translations={k: dict(v or {}) for k, v in (page.translations or {}).items()})
            page_remap[page.pk] = pages[page.pk].pk
        for block in site.blocks.order_by('order', 'id'):
            new = SiteBlock.objects.create(
                site=copy, page=pages[block.page_id], kind=block.kind, order=block.order, title=block.title,
                in_menu=block.in_menu,
                data=dict(block.data or {}), image=block.image.name if block.image else None,
                site_survey=links.get(block.site_survey_id))
            tr = {lang: dict(row or {}) for lang, row in (block.translations or {}).items()}
            for f in block.files.all():
                nf = SiteFile.objects.create(block=new, file=f.file.name, title=f.title, size=f.size,
                                             content_type=f.content_type, order=f.order)
                for row in tr.values():  # file titles follow the file to its new pk
                    if f'file:{f.pk}' in row:
                        row[f'file:{nf.pk}'] = row.pop(f'file:{f.pk}')
            # Hashes are keyed by block id; the copy's are the original's under the new ids.
            new.translations = tr
            new.save(update_fields=['translations'])
            remap[block.pk] = new.pk
            files_remap.update({f'file:{a}': f'file:{b}' for a, b in zip(
                block.files.order_by('order', 'id').values_list('pk', flat=True),
                new.files.order_by('order', 'id').values_list('pk', flat=True))})
        hashes = {}
        for lang, keys in (site.translation_sources or {}).items():
            out = {}
            for key, value in keys.items():
                parts = key.split(':', 2)
                if parts[0] == 'block' and len(parts) == 3 and parts[1].isdigit() and int(parts[1]) in remap:
                    field = files_remap.get(parts[2], parts[2])
                    out[f'block:{remap[int(parts[1])]}:{field}'] = value
                elif parts[0] == 'page' and len(parts) == 3 and parts[1].isdigit() and int(parts[1]) in page_remap:
                    out[f'page:{page_remap[int(parts[1])]}:{parts[2]}'] = value
                elif parts[0] == 'site':
                    out[key] = value
            hashes[lang] = out
        copy.translation_sources = hashes
        copy.save(update_fields=['translation_sources'])
    return copy


# ─── surveys ──────────────────────────────────────────────────────────────────

def linkable_surveys(org):
    """The workspace's surveys a site may link: canonical, not trashed or archived."""
    from .models import SurveyHeader
    return (SurveyHeader.objects.filter(organization=org, deleted_at__isnull=True,
                                        canonical_survey__isnull=True, published_version__isnull=True)
            .exclude(status='archived').order_by('name'))


CARD_OPEN, CARD_UPCOMING, CARD_CLOSED, CARD_HIDDEN = 'open', 'upcoming', 'closed', 'hidden'


def survey_card(survey, now=None):
    """What a survey card shows, read from the survey now: {'state', 'url', 'results_url',
    'opens_at', 'closes_at', 'reason'}. `hidden` cards are not drawn on the public page;
    `reason` tells the builder why."""
    from . import schedule, share
    from .content_screening import is_held
    from .embedding import survey_url_on
    from .models import PublicResultsPage

    card = {'state': CARD_HIDDEN, 'url': '', 'results_url': '', 'opens_at': None,
            'closes_at': None, 'reason': ''}
    if survey.deleted_at is not None or survey.status == 'archived':
        card['reason'] = _('The survey is archived or in the trash.')
        return card
    if survey.status == 'published' and is_held(survey):
        card['reason'] = _('The survey is waiting for a safety review.')
        return card
    if survey.status in ('draft', 'testing'):
        card['state'] = CARD_UPCOMING
        return card
    phase = schedule.phase(survey, now=now)
    if phase == 'open':
        card.update(state=CARD_OPEN, url=survey_url_on(share.base(), survey), closes_at=survey.closes_at)
        return card
    if phase == 'before':
        card.update(state=CARD_UPCOMING, opens_at=survey.opens_at)
        return card
    card['state'] = CARD_CLOSED
    page = PublicResultsPage.objects.filter(survey=survey, is_published=True).only('slug').first()
    if page is not None:
        from django.urls import reverse
        card['results_url'] = share.base() + reverse('public_results', args=[page.slug])
    return card


# ─── page ─────────────────────────────────────────────────────────────────────

def blocks_for(site, page=None):
    """The blocks of one page (home when `page` is None), in order."""
    page = page or home_page(site)
    return list(page.blocks.select_related('site_survey__survey').prefetch_related('files')
                .order_by('order', 'id'))


def block_card(block, now=None, lang='en'):
    """What a block's template needs besides the block itself: the survey card, the event
    times, the results payload — or None. Shared by the public page and the builder canvas."""
    if block.kind == 'results':
        return results_payload(block, lang=lang)
    if block.kind == 'event':
        from . import site_events
        start = site_events.starts_at(block.data)
        if start is None:
            return None
        return {'starts_at': start, 'ends_at': site_events.ends_at(block.data),
                'tz': block.data.get('tz') or 'UTC', 'accepting': site_events.accepting(block, now=now),
                'seats_left': site_events.seats_left(block),
                'retention_days': site_events.RETENTION_DAYS}
    if block.kind == 'survey' and block.site_survey is not None:
        return survey_card(block.site_survey.survey, now=now)
    if block.kind == 'updates':
        return updates_card(block)
    return None


def page_blocks(site, page=None, now=None, lang='en'):
    """[(block, card-or-None)] as the public page draws them: incomplete blocks dropped,
    survey cards resolved and hidden ones dropped, results without a question dropped."""
    out = []
    for block in blocks_for(site, page):
        if not is_complete(block):
            continue
        card = block_card(block, now=now, lang=lang)
        if block.kind in ('results', 'updates') and card is None:
            continue
        if block.kind == 'survey' and (card is None or card['state'] == CARD_HIDDEN):
            continue
        out.append((block, card))
    return out


def map_layers(site, blocks):
    """{base map key: Leaflet entry} for the map blocks on the page, or {} (no Leaflet then).
    A key the workspace no longer resolves falls back to Streets."""
    from . import basemaps
    out = {}
    for block, _card in blocks:
        if block.kind != 'map':
            continue
        key = block.data.get('basemap') or 'streets'
        if key in out:
            continue
        base = basemaps.resolve(key, site.organization) or basemaps.resolve('streets', None)
        if base is not None:
            out[key] = base.leaflet()
    return out


# ─── results (change landing-results) ─────────────────────────────────────────

RESULTS_CACHE_SECONDS = 60


def results_question(survey, code):
    """The canonical survey's current question with `code` (top level, publishable), or None."""
    from .models import Question
    from .public_results import block_type_for_question
    q = (Question.objects.filter(survey_section__survey_header=survey, code=code,
                                 parent_question_id__isnull=True).first() if code else None)
    return q if q is not None and block_type_for_question(q) else None


def results_choices(org):
    """[(survey, [(value, question name, kind)])] for the picker: every publishable top-level
    question of the workspace's linkable surveys; value = '<survey uuid>:<code>'."""
    from .models import Question
    from .public_results import block_type_for_question
    out = []
    for survey in linkable_surveys(org):
        rows = []
        for q in (Question.objects.filter(survey_section__survey_header=survey, parent_question_id__isnull=True)
                  .order_by('survey_section__id', 'order_number')):
            kind = block_type_for_question(q)
            if kind and q.code:
                rows.append((f'{survey.uuid}:{q.code}', q.name, kind))
        if rows:
            out.append((survey, rows))
    return out


def results_payload(block, lang='en'):
    """The PublicResultsService payload of a results block, cached 60 s, or None when its
    question is gone. Same clean sessions and masking as /r/; no popups."""
    from types import SimpleNamespace

    from django.core.cache import cache

    from .models import PublicResultsPage
    from .public_results import PublicResultsService, block_type_for_question

    if block.site_survey is None:
        return None
    key = f'landing-results:{block.pk}:{block.updated_at.timestamp()}:{lang}'
    try:
        hit = cache.get(key)
    except Exception:  # noqa: BLE001 — a cache outage must not take the page down
        hit = None
    if hit is not None:
        return hit or None
    survey = block.site_survey.survey
    question = results_question(survey, block.data.get('question_code'))
    payload = None
    if question is not None:
        page = PublicResultsPage.objects.filter(survey=survey).only('k_anonymity_threshold').first()
        k = page.k_anonymity_threshold if page is not None else \
            PublicResultsPage._meta.get_field('k_anonymity_threshold').default
        service = PublicResultsService.for_survey(survey, k, lang=lang)
        fake = SimpleNamespace(
            id=f'r{block.pk}', block_type=block_type_for_question(question), viz=block.data.get('viz') or 'auto',
            custom_title={}, question=question, question_id=question.pk, geo_label_fields=[],
            basemap=block.data.get('basemap') or 'streets', content={}, image=None, is_hidden=False)
        payload = service._build_block(fake)
        if payload is not None:
            payload['responses'] = service.response_count()
            payload['k'] = service.k
    try:
        cache.set(key, payload or {}, RESULTS_CACHE_SECONDS)
    except Exception:  # noqa: BLE001
        pass
    return payload


def outline_label(block):
    """The outline row's text: the heading, else what the block shows."""
    if block.title:
        return block.title
    data = block.data if isinstance(block.data, dict) else {}
    if block.kind == 'survey' and block.site_survey_id:
        return block.site_survey.survey.name
    if block.kind == 'text':
        from django.utils.html import strip_tags
        return ' '.join(strip_tags(data.get('body') or '').split())[:60]
    if block.kind == 'button':
        return data.get('label') or ''
    if block.kind in ('image', 'video', 'map'):
        return data.get('caption') or ''
    return ''


def next_order(page):
    last = page.blocks.order_by('-order').values_list('order', flat=True).first()
    return 0 if last is None else last + 1


def renumber(rows):
    for i, row in enumerate(rows):
        if row.order != i:
            row.order = i
            row.save(update_fields=['order'])
