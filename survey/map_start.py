"""Where a new survey's map opens (change first-survey-onboarding).

One ordered chain, used by every creation path -- the one-click blank
endpoint, the create page's first `setView`, and through that page's hidden
fields the AI draft -- so the three can never open on different places:

    browser      coordinates the request carries. They are there only when the
                 creator's browser gave them: permission already granted, or
                 asked on the click that submitted the form. Never on page load.
    org_survey   the newest survey in the workspace that has a map start. A
                 consultant's second workspace has its own city, and an editor
                 who has never created anything still gets the workspace's map.
    country      `CF-IPCountry` from Render's Cloudflare edge (trusted only
                 under CLOUDFLARE_TRUSTED, like CF-Connecting-IP), else the
                 region of the first Accept-Language entry -- except `en-US`,
                 the stock-browser default that says nothing. Country centre,
                 zoom 5. City-level IP lookup would need a GeoIP database for a
                 point the browser gives better; not worth the dependency.
    world        (20, 0) at zoom 2. An honest "we do not know", unlike the
                 Berlin the create page used to start on.

`source` rides on `survey_created` as `map_source`, next to `map_touched`,
which is how we learn which rung works and how often creators then move the
map. Never raises; no network; at most one query.
"""
import logging
from collections import namedtuple

from django.conf import settings

from .country_centroids import centroid

logger = logging.getLogger(__name__)

StartPosition = namedtuple('StartPosition', 'lat lng zoom source')

SOURCE_BROWSER = 'browser'
SOURCE_ORG_SURVEY = 'org_survey'
SOURCE_COUNTRY = 'country'
SOURCE_WORLD = 'world'
SOURCES = (SOURCE_BROWSER, SOURCE_ORG_SURVEY, SOURCE_COUNTRY, SOURCE_WORLD)

ZOOM_BROWSER = 13
ZOOM_ORG_SURVEY = 12
ZOOM_COUNTRY = 5
WORLD = StartPosition(20.0, 0.0, 2, SOURCE_WORLD)


def browser_position(data):
    """`(lat, lng, zoom)` from posted `map_lat`/`map_lng`/`map_zoom`, or `None`.

    Lenient on zoom (missing -> ZOOM_BROWSER), strict on the point: anything
    that is not a finite pair inside the WGS84 box is treated as absent, so a
    scripted POST cannot park a survey at (999, 999).
    """
    try:
        lat = float(data.get('map_lat', ''))
        lng = float(data.get('map_lng', ''))
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    try:
        zoom = int(data.get('map_zoom') or ZOOM_BROWSER)
    except (TypeError, ValueError):
        zoom = ZOOM_BROWSER
    return lat, lng, max(1, min(zoom, 22))


def suggest_start_position(request, browser=None):
    """The chain above, for `request`. `browser` is `(lat, lng, zoom)` or `None`."""
    if browser:
        lat, lng, zoom = browser
        return StartPosition(lat, lng, zoom, SOURCE_BROWSER)

    found = _org_survey_position(getattr(request, 'active_org', None))
    if found:
        return found

    code = _country_code(request)
    point = centroid(code)
    if point:
        return StartPosition(point[0], point[1], ZOOM_COUNTRY, SOURCE_COUNTRY)

    return WORLD


def _org_survey_position(org):
    if org is None:
        return None
    from .models import SurveyHeader
    try:
        row = (SurveyHeader.objects
               .filter(organization=org, is_canonical=True, deleted_at__isnull=True,
                       start_map_postion__isnull=False)
               .order_by('-id')
               .values_list('start_map_postion', 'start_map_zoom')
               .first())
    except Exception:  # noqa: BLE001 - a suggestion must never fail a request
        logger.exception('map_start: org survey lookup failed')
        return None
    if not row or row[0] is None:
        return None
    point, zoom = row
    return StartPosition(point.y, point.x, zoom or ZOOM_ORG_SURVEY, SOURCE_ORG_SURVEY)


def _country_code(request):
    meta = getattr(request, 'META', {}) or {}
    if getattr(settings, 'CLOUDFLARE_TRUSTED', False):
        code = (meta.get('HTTP_CF_IPCOUNTRY') or '').strip().upper()
        if len(code) == 2 and code.isalpha():
            return code
    return _accept_language_region(meta.get('HTTP_ACCEPT_LANGUAGE', ''))


# The locale most browsers ship with, whoever and wherever the person is: a
# creator in Bishkek with a stock Chrome sends `en-US` and would land on
# Kansas. It says nothing about where they are, so it is treated as silence;
# `de-AT`, `pt-BR`, `fr-CA` are choices somebody made and still count.
UNINFORMATIVE_LOCALES = ('en-US',)


def _accept_language_region(header):
    """`AT` from `de-AT,de;q=0.9`; `''` when the first entry names no region
    or is the browser default `en-US`."""
    first = (header or '').split(',', 1)[0].split(';', 1)[0].strip()
    if first in UNINFORMATIVE_LOCALES:
        return ''
    parts = first.replace('_', '-').split('-')
    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            return part.upper()
    return ''
