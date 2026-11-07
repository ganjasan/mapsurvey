"""Landing pages (change landing-core, #576; epic #348).

A `Landing` is a workspace's public page for an engagement at /p/<slug>/. Its content is an
ordered list of `LandingBlock`s of a closed set of kinds; every write of a block's data goes
through `clean_block`, so what the builder saves is exactly what the templates can draw.
A new kind (documents, map, results, events — #577–#579) is one entry in `BLOCK_KINDS`, its
cleaner here and its two templates (`landings/blocks/<kind>.html` for the page,
`landings/forms/<kind>.html` for the builder) — never a column.

Surveys are linked many-to-many through `LandingSurvey` (canonical surveys of the landing's
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
IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp', 'image/gif')

ACTING_ROLES = ('owner', 'admin', 'editor')
FEATURE = 'landing_pages'


class BlockInvalid(Exception):
    """`errors` is {field: message}."""

    def __init__(self, errors):
        super().__init__(errors)
        self.errors = errors


# ─── block kinds ──────────────────────────────────────────────────────────────

# key → (label, icon, group) for the "Add block" picker, in picker order.
BLOCK_KINDS = {
    'text': (gettext_lazy('Text'), 'fas fa-align-left', 'content'),
    'faq': (gettext_lazy('FAQ'), 'far fa-question-circle', 'content'),
    'timeline': (gettext_lazy('Timeline'), 'fas fa-stream', 'content'),
    'image': (gettext_lazy('Image'), 'far fa-image', 'media'),
    'video': (gettext_lazy('Video'), 'fab fa-youtube', 'media'),
    'map': (gettext_lazy('Map'), 'fas fa-draw-polygon', 'media'),
    'results': (gettext_lazy('Results'), 'fas fa-chart-bar', 'media'),
    'documents': (gettext_lazy('Documents'), 'far fa-file-pdf', 'participation'),
    'event': (gettext_lazy('Event'), 'far fa-calendar-check', 'participation'),
    'survey': (gettext_lazy('Survey card'), 'fas fa-map-marked-alt', 'participation'),
    'button': (gettext_lazy('Button'), 'fas fa-link', 'participation'),
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


def _plain(value, cap):
    return ' '.join(str(value or '').split())[:cap]


def _rich(value, cap):
    html = coerce_creator_html(str(value or ''))
    return html[:cap] if html else ''


def _is_empty_html(html):
    return not re.sub(r'<[^>]+>|&nbsp;|\s', '', html or '')


def _clean_text(raw, errors):
    body = _rich(raw.get('body'), RICH_TEXT_MAX)
    if _is_empty_html(body):
        errors['body'] = _('Write some text.')
    return {'body': body}


def _clean_image(raw, errors):
    return {'alt': _plain(raw.get('alt'), 200), 'caption': _plain(raw.get('caption'), 300)}


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
    return {'url': url[:500], 'embed': embed, 'caption': _plain(raw.get('caption'), 300)}


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


def _clean_documents(raw, errors):
    # The files are LandingFile rows (change landing-documents-map); the block keeps no data.
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
            'caption': _plain(raw.get('caption'), 300)}


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


_CLEANERS = {
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
}


def clean_block(kind, raw, org=None):
    """(data, errors) for a block of `kind` from the posted `raw` dict. `data` carries only
    the kind's keys, trimmed and capped; rich text has passed `coerce_creator_html`. `org`
    lets the map cleaner check its base map against the workspace's."""
    if kind not in _CLEANERS:
        return {}, {'kind': _('Unknown block type.')}
    errors = {}
    raw = raw if isinstance(raw, dict) else {}
    if kind == 'map':
        return _clean_map(raw, errors, org=org), errors
    if kind == 'results':
        return _clean_results(raw, errors, org=org), errors
    data = _CLEANERS[kind](raw, errors)
    return data, errors


def clean_title(value):
    return _plain(value, TITLE_MAX)


def check_image(upload):
    """An error message for an uploaded picture, or ''."""
    if upload is None:
        return ''
    if upload.size > IMAGE_MAX_BYTES:
        return _('The picture is larger than 5 MB.')
    if (getattr(upload, 'content_type', '') or '').lower() not in IMAGE_TYPES:
        return _('Upload a JPEG, PNG, WebP or GIF picture.')
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

def slug_error(slug, landing=None):
    """A field error for `slug`, or ''."""
    from .models import Landing
    if not (SLUG_MIN <= len(slug) <= SLUG_MAX) or not SLUG_RE.match(slug):
        return _('Use 3–64 lowercase letters, digits and dashes.')
    if slug in RESERVED_SLUGS:
        return _('This address is reserved. Pick another.')
    taken = Landing.objects.filter(slug=slug)
    if landing is not None and landing.pk:
        taken = taken.exclude(pk=landing.pk)
    if taken.exists():
        return _('Another landing page already uses this address.')
    return ''


def unique_slug(title):
    from .models import Landing
    base = slugify(title)[:SLUG_MAX - 4].strip('-') or 'landing'
    if len(base) < SLUG_MIN or base in RESERVED_SLUGS:
        base = f'{base}-page'.strip('-')
    slug, n = base, 2
    while Landing.objects.filter(slug=slug).exists():
        slug = f'{base}-{n}'
        n += 1
    return slug


# ─── surveys ──────────────────────────────────────────────────────────────────

def linkable_surveys(org):
    """The workspace's surveys a landing may link: canonical, not trashed or archived."""
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

def blocks_for(landing):
    return list(landing.blocks.select_related('landing_survey__survey').prefetch_related('files')
                .order_by('order', 'id'))


def page_blocks(landing, now=None, lang='en'):
    """[(block, card-or-None)] as the public page draws them: survey cards resolved, hidden
    survey cards dropped, documents blocks without files dropped."""
    out = []
    for block in blocks_for(landing):
        if block.kind == 'documents' and not block.files.all():
            continue
        if block.kind == 'results':
            card = results_payload(block, lang=lang)
            if card is None:
                continue
            out.append((block, card))
            continue
        card = None
        if block.kind == 'event':
            from . import landing_events
            start = landing_events.starts_at(block.data)
            if start is None:
                continue
            card = {'starts_at': start, 'ends_at': landing_events.ends_at(block.data),
                    'tz': block.data.get('tz') or 'UTC', 'accepting': landing_events.accepting(block, now=now),
                    'seats_left': landing_events.seats_left(block),
                    'retention_days': landing_events.RETENTION_DAYS}
        if block.kind == 'survey':
            if block.landing_survey is None:
                continue
            card = survey_card(block.landing_survey.survey, now=now)
            if card['state'] == CARD_HIDDEN:
                continue
        out.append((block, card))
    return out


def map_layers(landing, blocks):
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
        base = basemaps.resolve(key, landing.organization) or basemaps.resolve('streets', None)
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

    if block.landing_survey is None:
        return None
    key = f'landing-results:{block.pk}:{block.updated_at.timestamp()}:{lang}'
    try:
        hit = cache.get(key)
    except Exception:  # noqa: BLE001 — a cache outage must not take the page down
        hit = None
    if hit is not None:
        return hit or None
    survey = block.landing_survey.survey
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


def nav_items(blocks):
    return [(b.anchor, b.title) for b, _card in blocks if b.title]


def next_order(landing):
    last = landing.blocks.order_by('-order').values_list('order', flat=True).first()
    return 0 if last is None else last + 1


def renumber(rows):
    for i, row in enumerate(rows):
        if row.order != i:
            row.order = i
            row.save(update_fields=['order'])
