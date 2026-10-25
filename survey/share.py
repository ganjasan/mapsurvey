"""Distributing a survey without a request: the links, the embed snippet, a QR
code, campaign (tracked) links and the embed allow-list (change
api-v2-distribution, #410). The REST API and the MCP tools call these; the
editor's Share page keeps its own views and builds the same URLs.

Every URL is built on `SITE_URL` -- the API has no request host worth trusting.
Tracked links and embed hosts live on the canonical survey, as on the Share page.
"""
import io

from django.conf import settings
from django.urls import reverse

from .audit import record as audit_record
from .embedding import InvalidHost, normalise_allowed_hosts, snippet_html, survey_url_on
from .models import PublicResultsPage, TrackedLink
from .versioning import canonical_of

MAX_TRACKED_LINKS = 200
UTM_MAX = 100
QR_SIZE_MIN, QR_SIZE_MAX, QR_SIZE_DEFAULT = 1, 40, 10


class ShareError(Exception):
    """A refusal the API maps to its envelope: `code`, a creator-facing message,
    and the fields it concerns."""

    def __init__(self, code, message, fields=None, status=400):
        super().__init__(message)
        self.code, self.message, self.fields, self.status = code, message, fields or {}, status


def base():
    return (settings.SITE_URL or '').rstrip('/')


def is_shareable(survey):
    return survey.status == 'published'


def _reason(survey):
    return {
        'draft': 'The survey is a draft: only you and your collaborators can open it. Publish it to share.',
        'testing': 'The survey is in testing: it opens only through the test link.',
        'closed': 'The survey is closed: the link shows a "closed" page.',
    }.get(survey.status, 'The survey is not published.')


def share_info(survey, can_see_test_link=False):
    canonical = canonical_of(survey)
    shareable = is_shareable(canonical)
    info = {
        'status': canonical.status,
        'shareable': shareable,
        'reason': None if shareable else _reason(canonical),
        'url': None, 'results_url': None, 'embed_snippet': None,
        'embed_hosts': list(canonical.embed_allowed_hosts or []),
        'test_url': None,
    }
    if shareable:
        info['url'] = survey_url_on(base(), canonical)
        info['embed_snippet'] = snippet_html(None, canonical, base=base())
        page = PublicResultsPage.objects.filter(survey=canonical, is_published=True).first()
        if page is not None:
            info['results_url'] = base() + reverse('public_results', args=[page.slug])
    if canonical.status == 'testing' and can_see_test_link:
        info['test_url'] = canonical.get_test_url(base())
    return info


# ─── QR ───────────────────────────────────────────────────────────────────────

def qr_target(survey, link_id=None):
    canonical = canonical_of(survey)
    if not is_shareable(canonical):
        raise ShareError('not_shareable', _reason(canonical), status=409)
    if link_id is None:
        return survey_url_on(base(), canonical)
    link = TrackedLink.objects.filter(pk=link_id, survey=canonical).first()
    if link is None:
        raise ShareError('not_found', 'No such tracked link on this survey.', status=404)
    return link.build_url(base())


def qr_image(url, fmt='png', size=QR_SIZE_DEFAULT):
    """(bytes, content type) of a QR code of `url`. segno: pure Python, no Pillow."""
    import segno
    size = max(QR_SIZE_MIN, min(QR_SIZE_MAX, int(size or QR_SIZE_DEFAULT)))
    qr = segno.make(url, error='m')
    buf = io.BytesIO()
    if fmt == 'svg':
        qr.save(buf, kind='svg', scale=size, border=4, xmldecl=False)
        return buf.getvalue(), 'image/svg+xml'
    qr.save(buf, kind='png', scale=size, border=4)
    return buf.getvalue(), 'image/png'


# ─── Tracked links ────────────────────────────────────────────────────────────

def _counts(canonical):
    from .analytics import PerformanceAnalyticsService
    rows = PerformanceAnalyticsService(canonical).get_campaign_breakdown()
    return {(r['utm_source'] or '', r['utm_medium'] or '', r['utm_campaign'] or ''): r for r in rows}


def _link_out(link, counts):
    row = counts.get((link.utm_source, link.utm_medium or '', link.utm_campaign or ''), {})
    return {'id': link.pk, 'utm_source': link.utm_source, 'utm_medium': link.utm_medium,
            'utm_campaign': link.utm_campaign, 'url': link.build_url(base()),
            'created_at': link.created_at, 'started': row.get('started', 0),
            'completed': row.get('completed', 0)}


def list_links(survey):
    canonical = canonical_of(survey)
    counts = _counts(canonical)
    return [_link_out(link, counts) for link in TrackedLink.objects.filter(survey=canonical)]


def create_link(actor, survey, utm_source, utm_medium='', utm_campaign=''):
    canonical = canonical_of(survey)
    values = {'utm_source': (utm_source or '').strip(), 'utm_medium': (utm_medium or '').strip(),
              'utm_campaign': (utm_campaign or '').strip()}
    fields = {k: [f'At most {UTM_MAX} characters.'] for k, v in values.items() if len(v) > UTM_MAX}
    if not values['utm_source']:
        fields['utm_source'] = ['Required.']
    if fields:
        raise ShareError('validation', 'Check the link fields.', fields)
    if TrackedLink.objects.filter(survey=canonical).count() >= MAX_TRACKED_LINKS:
        raise ShareError('limit_reached', f'A survey holds at most {MAX_TRACKED_LINKS} tracked links.', status=409)
    link = TrackedLink.objects.create(survey=canonical, **values)
    audit_record(actor, 'tracked_link_create', canonical, link_id=link.pk, utm_source=link.utm_source)
    return _link_out(link, _counts(canonical))


def delete_link(actor, survey, link_id):
    canonical = canonical_of(survey)
    link = TrackedLink.objects.filter(pk=link_id, survey=canonical).first()
    if link is None:
        raise ShareError('not_found', 'No such tracked link on this survey.', status=404)
    audit_record(actor, 'tracked_link_delete', canonical, link_id=link.pk, utm_source=link.utm_source)
    link.delete()


# ─── Embed hosts ──────────────────────────────────────────────────────────────

def set_embed_hosts(actor, survey, hosts):
    canonical = canonical_of(survey)
    try:
        cleaned = normalise_allowed_hosts(list(hosts or []))
    except InvalidHost as exc:
        raise ShareError('validation', f'Not a host name: {exc}', {'hosts': [str(exc)]})
    canonical.embed_allowed_hosts = cleaned
    canonical.save(update_fields=['embed_allowed_hosts', 'updated_at'])
    audit_record(actor, 'embed_hosts_set', canonical, hosts=cleaned)
    return cleaned
