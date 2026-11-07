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
}


def clean_block(kind, raw):
    """(data, errors) for a block of `kind` from the posted `raw` dict. `data` carries only
    the kind's keys, trimmed and capped; rich text has passed `coerce_creator_html`."""
    if kind not in _CLEANERS:
        return {}, {'kind': _('Unknown block type.')}
    errors = {}
    data = _CLEANERS[kind](raw if isinstance(raw, dict) else {}, errors)
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
    return list(landing.blocks.select_related('landing_survey__survey').order_by('order', 'id'))


def page_blocks(landing, now=None):
    """[(block, card-or-None)] as the public page draws them: survey cards resolved, hidden
    survey cards dropped."""
    out = []
    for block in blocks_for(landing):
        card = None
        if block.kind == 'survey':
            if block.landing_survey is None:
                continue
            card = survey_card(block.landing_survey.survey, now=now)
            if card['state'] == CARD_HIDDEN:
                continue
        out.append((block, card))
    return out


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
