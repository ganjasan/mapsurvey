"""Clients for the external acquisition sources feeding the top of the funnel.

Two providers, deliberately independent (design D6): Google Search Console for
impressions/clicks, Plausible for landing traffic and its channel mix. Each returns
plain per-day dicts ready for `AcquisitionDaily`, and each fails on its own without
taking the other down.

An absent credential is not an error here -- it is the `NotConfigured` condition, a
state the dashboard renders as "not configured" rather than as a zero (D6). Only the
sync command talks to these clients; nothing on a request path does (D1).
"""

import datetime as dt
import json
import logging

import requests
from django.conf import settings

from .models import AcquisitionDaily

logger = logging.getLogger(__name__)

# GSC revises recent data for several days; anything newer than this is not final.
GSC_LAG_DAYS = 2

# Plausible Stats API v1 (aggregate/breakdown endpoints).
PLAUSIBLE_API_BASE = 'https://plausible.io/api/v1/stats'
PLAUSIBLE_TIMEOUT = 30

GSC_SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']


class NotConfigured(Exception):
    """The provider has no usable credential. Distinct from a request failure."""


class ProviderError(Exception):
    """The provider is configured but the fetch failed."""


def _non_marketing_prefixes():
    """URL prefixes that are NOT marketing pages.

    Defined by exclusion rather than inclusion (design D3): the set of app prefixes
    is short and stable, while the set of marketing landings grows with every SEO
    change -- an allow-list would silently drop each new landing out of the funnel.

    Survey pages matter most here: their impressions are our customers' respondents
    finding *their* survey, which can never convert into a registration. In the last
    90 days one customer survey drew more impressions than `/trust/`.
    """
    return list(getattr(settings, 'ACQUISITION_NON_MARKETING_PREFIXES', ()))


# -- Google Search Console ----------------------------------------------------


def _gsc_credentials():
    """Service-account credentials from the environment, falling back to a key file.

    Production has no secret-file primitive, so the key travels as JSON in
    `GSC_SERVICE_ACCOUNT_JSON`; the file path stays for local development, where the
    key already lives at `~/.config/mapsurvey/…json` (design D6).
    """
    from google.oauth2 import service_account

    raw = getattr(settings, 'GSC_SERVICE_ACCOUNT_JSON', '')
    if raw:
        try:
            info = json.loads(raw)
        except ValueError as exc:
            raise NotConfigured(f'GSC_SERVICE_ACCOUNT_JSON is not valid JSON: {exc}')
        return service_account.Credentials.from_service_account_info(info, scopes=GSC_SCOPES)

    path = getattr(settings, 'GSC_KEY_PATH', '')
    if path:
        try:
            return service_account.Credentials.from_service_account_file(path, scopes=GSC_SCOPES)
        except OSError as exc:
            raise NotConfigured(f'GSC key file unreadable: {exc}')

    raise NotConfigured('neither GSC_SERVICE_ACCOUNT_JSON nor GSC_KEY_PATH is set')


def gsc_service():
    """An authenticated Search Console client, or NotConfigured."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:                       # dependency not installed
        raise NotConfigured(f'google-api-python-client missing: {exc}')

    creds = _gsc_credentials()
    site = getattr(settings, 'GSC_SITE', '')
    if not site:
        raise NotConfigured('GSC_SITE is not set')
    try:
        return build('searchconsole', 'v1', credentials=creds, cache_discovery=False), site
    except Exception as exc:                         # auth/discovery failure
        raise ProviderError(f'building the Search Console client failed: {exc}')


def gsc_window(days, today=None):
    """The (start, end) dates to request, accounting for GSC's ~2-day lag."""
    today = today or dt.date.today()
    end = today - dt.timedelta(days=GSC_LAG_DAYS)
    return end - dt.timedelta(days=days - 1), end


# Matches every URL on the property. Present so the whole-property query carries a
# page filter too, which forces GSC into the same aggregation mode as the filtered
# marketing query -- see MATCH_ALL_PAGES usage below.
MATCH_ALL_PAGES = '^https?://'


def _gsc_query(service, site, start, end, exclude_prefixes=None):
    """Per-date rows from the Search Analytics API, page-level aggregation.

    Both the whole-property and the marketing query carry a page filter, and that is
    deliberate: GSC aggregates by *property* when no page dimension or filter is
    involved (one search result counts once even if several of our pages appeared) and
    by *page* as soon as one is. The two modes yield different totals for the same
    window -- measured on 14 live days: 1329 property-level vs 1717 page-level.

    Mixing them would make the marketing segment exceed the whole-property segment,
    which is arithmetically impossible and would break the funnel. So the whole-property
    query filters on a match-everything expression to stay in page-level mode, keeping
    the two segments subtractable (marketing + app pages ~= whole).

    Consequence to remember when cross-checking: the whole-property number here is
    page-level and will read higher than the total shown in the Search Console UI,
    which is property-level.
    """
    filters = [{
        'dimension': 'page',
        'operator': 'excludingRegex' if exclude_prefixes else 'includingRegex',
        'expression': (exclusion_regex(exclude_prefixes) if exclude_prefixes
                       else MATCH_ALL_PAGES),
    }]
    body = {
        'startDate': start.isoformat(),
        'endDate': end.isoformat(),
        'dimensions': ['date'],
        'rowLimit': 1000,
        'dimensionFilterGroups': [{'filters': filters}],
    }
    try:
        resp = service.searchanalytics().query(siteUrl=site, body=body).execute()
    except Exception as exc:
        raise ProviderError(f'Search Analytics query failed: {exc}')
    return resp.get('rows', [])


def exclusion_regex(prefixes):
    """An anchored regex matching any URL under the given path prefixes.

    GSC filters on the full URL, so the prefix is matched after the host. Prefixes
    are treated as literals; a URL matching any of them is excluded.
    """
    import re

    parts = [re.escape(p.rstrip('/')) for p in prefixes if p and p != '/']
    return f"^https?://[^/]+({'|'.join(parts)})/"


def fetch_gsc(days, today=None):
    """Per-day GSC metrics for the whole property and for marketing pages.

    Returns a list of `AcquisitionDaily` field dicts. Raises NotConfigured when the
    credential is absent, ProviderError when the fetch fails.
    """
    service, site = gsc_service()
    start, end = gsc_window(days, today=today)

    def rows_for(segment, exclude=None):
        out = []
        for row in _gsc_query(service, site, start, end, exclude):
            keys = row.get('keys') or []
            if not keys:
                continue
            out.append({
                'source': 'gsc',
                'date': dt.date.fromisoformat(keys[0]),
                'segment': segment,
                'impressions': int(row.get('impressions') or 0),
                'clicks': int(row.get('clicks') or 0),
                'ctr': row.get('ctr'),
                'position': row.get('position'),
            })
        return out

    result = rows_for(AcquisitionDaily.SEGMENT_ALL)
    exclude = _non_marketing_prefixes()
    if exclude:
        result += rows_for(AcquisitionDaily.SEGMENT_MARKETING, exclude)
    else:
        logger.warning(
            'ACQUISITION_NON_MARKETING_PREFIXES is empty; skipping the marketing segment'
        )
    return result


# -- Plausible ----------------------------------------------------------------


def _plausible_config():
    key = getattr(settings, 'PLAUSIBLE_API_KEY', '')
    site_id = getattr(settings, 'PLAUSIBLE_SITE_ID', '')
    if not key or not site_id:
        raise NotConfigured('PLAUSIBLE_API_KEY and PLAUSIBLE_SITE_ID must both be set')
    return key, site_id


def _plausible_get(path, params):
    key, site_id = _plausible_config()
    params = dict(params, site_id=site_id)
    try:
        resp = requests.get(
            f'{PLAUSIBLE_API_BASE}/{path}',
            params=params,
            headers={'Authorization': f'Bearer {key}'},
            timeout=PLAUSIBLE_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ProviderError(f'Plausible request failed: {exc}')
    if resp.status_code == 401:
        raise NotConfigured('Plausible rejected the API key (401)')
    if resp.status_code == 402:
        raise NotConfigured('Plausible plan does not include Stats API access (402)')
    if resp.status_code >= 400:
        raise ProviderError(f'Plausible returned {resp.status_code}: {resp.text[:200]}')
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError(f'Plausible returned non-JSON: {exc}')


def plausible_window(days, today=None):
    """Plausible reports complete days, so the window ends yesterday."""
    today = today or dt.date.today()
    end = today - dt.timedelta(days=1)
    return end - dt.timedelta(days=days - 1), end


def _date_range_param(start, end):
    return f'{start.isoformat()},{end.isoformat()}'


def fetch_plausible(days, today=None):
    """Per-day Plausible metrics: whole site, landing page, and referrer channels.

    Returns a list of `AcquisitionDaily` field dicts. The channel breakdown is
    fetched per day, because Plausible aggregates a breakdown over the whole range
    and we store daily rows.
    """
    _plausible_config()                              # fail fast on missing config
    start, end = plausible_window(days, today=today)
    rows = []

    # Whole-site and landing-page daily series.
    for segment, filters in (
        (AcquisitionDaily.SEGMENT_ALL, None),
        (AcquisitionDaily.SEGMENT_LANDING, 'event:page==/'),
    ):
        params = {
            'period': 'custom',
            'date': _date_range_param(start, end),
            'metrics': 'visitors,pageviews',
        }
        if filters:
            params['filters'] = filters
        data = _plausible_get('timeseries', params)
        for row in data.get('results', []) or []:
            if not row.get('date'):
                continue
            rows.append({
                'source': 'plausible',
                'date': dt.date.fromisoformat(row['date']),
                'segment': segment,
                'visitors': row.get('visitors'),
                'pageviews': row.get('pageviews'),
            })

    # Referrer channels, one request per day (breakdowns are range-aggregated).
    day = start
    while day <= end:
        data = _plausible_get('breakdown', {
            'period': 'custom',
            'date': _date_range_param(day, day),
            'property': 'visit:source',
            'metrics': 'visitors,pageviews',
            'limit': 50,
        })
        for row in data.get('results', []) or []:
            channel = (row.get('source') or 'Direct / None').strip()
            rows.append({
                'source': 'plausible',
                'date': day,
                'segment': f'{AcquisitionDaily.CHANNEL_PREFIX}{channel}'[:60],
                'visitors': row.get('visitors'),
                'pageviews': row.get('pageviews'),
            })
        day += dt.timedelta(days=1)

    return rows


# -- demo survey resolution ---------------------------------------------------


def demo_survey_uuid():
    """The UUID embedded in `DEMO_SURVEY_URL`, or None if absent/malformed."""
    import re
    import uuid as uuid_module

    url = getattr(settings, 'DEMO_SURVEY_URL', '') or ''
    match = re.search(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', url, re.I
    )
    if not match:
        return None
    try:
        return uuid_module.UUID(match.group(0))
    except ValueError:
        return None


def demo_survey():
    """The `SurveyHeader` behind `DEMO_SURVEY_URL`, or None.

    None covers every way this can be absent -- unset URL, malformed URL, deleted
    survey -- because none of them may raise on a respondent's request path (D4).
    """
    from .models import SurveyHeader

    survey_uuid = demo_survey_uuid()
    if survey_uuid is None:
        return None
    return SurveyHeader.objects.filter(uuid=survey_uuid).first()


def demo_survey_id():
    """The demo survey's primary key, cached, or None.

    Cached because this is consulted on every respondent session creation across the
    whole platform. The cache key includes the configured URL, so changing the setting
    (or overriding it in a test) resolves afresh rather than serving a stale survey.
    """
    from django.core.cache import cache

    url = getattr(settings, 'DEMO_SURVEY_URL', '') or ''
    if not url:
        return None
    key = f'demo_survey_id:{url}'
    try:
        cached = cache.get(key)
    except Exception:                                # cache backend down
        cached = None
    if cached is not None:
        return cached or None                        # 0 is the cached "no such survey"

    survey = demo_survey()
    resolved = survey.pk if survey else 0
    try:
        cache.set(key, resolved, 300)
    except Exception:
        pass
    return resolved or None


def record_demo_open(session, request=None):
    """Record that a demo session was started, and by whom if signed in.

    Written only for the demo survey; every other survey's sessions stay free of
    respondent identity (design D4). Failure-tolerant on purpose: analytics must never
    break a respondent's survey.
    """
    from .models import DemoOpen

    try:
        demo_id = demo_survey_id()
        if demo_id is None or session.survey_id != demo_id:
            return None
        user = getattr(request, 'user', None) if request is not None else None
        if user is not None and not getattr(user, 'is_authenticated', False):
            user = None
        return DemoOpen.objects.create(session=session, user=user)
    except Exception:
        logger.exception('recording a demo open failed for session %s', session.pk)
        return None
