"""The study area the Wizard gives a new survey (change map-layers-study-area, D8b; spec
ai-survey-generation "The Wizard sets the study area").

The create page shows the boundary of the place the brief names and posts what the creator kept:
`study_area_mode` is `set` (the outline in `study_area_geometry`, maybe edited), `off` (they removed
it) or `auto` (nothing at hand yet — the page had no answer from the lookup, or no JavaScript).
`auto` is resolved during generation from the place the model read from the brief. Every lookup
is best effort: a failure leaves the survey without a study area, never fails the draft.
"""
import json
import logging
from types import SimpleNamespace

from .services import study_area as svc_area
from .services.context import Actor
from .services.errors import ValidationFailed

logger = logging.getLogger(__name__)

MODE_AUTO, MODE_SET, MODE_OFF = 'auto', 'set', 'off'
MODES = (MODE_AUTO, MODE_SET, MODE_OFF)
SURFACE_WIZARD = 'wizard'


def _truthy(value):
    return str(value or '').lower() in ('1', 'true', 'on', 'yes')


def from_post(post):
    """The creator's choice from a create-page POST, as a JSON-safe dict (it rides to Celery)."""
    mode = post.get('study_area_mode') or MODE_AUTO
    if mode not in MODES:
        mode = MODE_AUTO
    geometry = None
    if mode == MODE_SET:
        try:
            geometry = json.loads(post.get('study_area_geometry') or 'null')
        except ValueError:
            geometry = None
        if not isinstance(geometry, dict):
            mode, geometry = MODE_AUTO, None
    return {
        'mode': mode,
        'geometry': geometry,
        'place_name': (post.get('study_area_place') or '')[:255],
        'osm_ref': (post.get('study_area_osm_ref') or '')[:40],
        'refuse_outside': _truthy(post.get('study_area_refuse')),
    }


def _best(candidates):
    """The candidate to outline: the first area (a boundary) Nominatim ranks, else its first hit."""
    for item in candidates:
        if item.get('kind') == 'polygon' and item.get('osm_ref'):
            return item
    return next((item for item in candidates if item.get('osm_ref')), None)


def boundary_for(query=None, osm_ref=None, width=None, language='en'):
    """The outline the Wizard proposes, cleaned and capped like a saved study area:
    {geometry, name, kind, osm_ref, type, km2} or None. Raises LookupUnavailable."""
    from .study_area_lookup import DEFAULT_WIDTH, candidate_outline, search
    width = width or DEFAULT_WIDTH
    item = None
    if not osm_ref:
        item = _best(search(query or '', language))
        if item is None:
            return None
        osm_ref = item['osm_ref']
    found = candidate_outline(osm_ref, width)
    if found is None or not found.get('geometry'):
        return None
    try:
        multi = svc_area.clean_geometry(found['geometry'])
    except ValidationFailed:
        return None
    return {
        'geometry': json.loads(multi.geojson),
        'name': found.get('name') or (item or {}).get('name', ''),
        'kind': found.get('kind') or '',
        'osm_ref': osm_ref,
        'type': (item or {}).get('type', ''),
        'width': width if found.get('kind') == 'line' else None,
        'km2': svc_area.area_km2(SimpleNamespace(geometry=multi)),
    }


def resolve(spec, location):
    """`spec` with an outline to set, or None when the survey gets no study area. Network lookups
    happen here, so callers run it outside any database transaction."""
    from django.conf import settings
    if not settings.MAP_REFERENCE_LAYERS or not spec or spec.get('mode') == MODE_OFF:
        return None
    if spec.get('mode') == MODE_SET and spec.get('geometry'):
        return spec
    if not location:
        return None
    from .study_area_lookup import LookupUnavailable
    try:
        found = boundary_for(query=location)
    except LookupUnavailable:
        logger.info('Wizard study area: lookup unavailable for %r', location)
        return None
    except Exception:  # noqa: BLE001 — a lookup must never fail the draft
        logger.exception('Wizard study area lookup failed for %r', location)
        return None
    if found is None:
        return None
    return {**spec, 'mode': MODE_SET, 'geometry': found['geometry'],
            'place_name': found['name'], 'osm_ref': found['osm_ref']}


def apply(user, survey, spec):
    """Set the resolved study area on the new survey; returns the StudyArea or None."""
    if not spec or not spec.get('geometry'):
        return None
    try:
        return svc_area.set_area(
            Actor(user=user, surface=SURFACE_WIZARD), survey, spec['geometry'],
            source='place', place_name=spec.get('place_name', ''), osm_ref=spec.get('osm_ref', ''),
            fog=True, refuse_outside=bool(spec.get('refuse_outside')),
        )
    except ValidationFailed as exc:
        logger.info('Wizard study area refused: %s', exc.message)
    except Exception:  # noqa: BLE001 — the draft exists already; the area is a bonus
        logger.exception('Wizard study area could not be set')
    return None
