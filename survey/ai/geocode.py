"""One bounded place lookup for AI-drafted surveys.

The model returns the place a brief is about as a *name* (see `schema.py`);
this turns it into a start position. Photon rather than Mapbox because it is
what the map search and the create-page prefill already use, needs no key,
and cannot bill a worker that retries. Everything that can go wrong returns
`None`: the map is the one part of a draft that must never fail the draft.
"""
import logging

import requests

logger = logging.getLogger(__name__)

PHOTON_URL = 'https://photon.komoot.io/api/'
TIMEOUT_SECONDS = 4
USER_AGENT = 'Mapsurvey/1.0 (+https://mapsurvey.org)'

# Same ladder as the client-side prefill on the create page, so a place lands
# at the same zoom whichever path resolved it.
ZOOM_DEFAULT = 12
ZOOM_BY_TYPE = {
    'country': 6,
    'state': 9,
    'county': 9,
}


def geocode_place(name):
    """Return `(lat, lng, zoom)` for a place name, or `None`.

    Never raises. One request, one result (`limit=1`); Photon's ranking is
    good enough for the "<locality>, <region>, <country>" strings the prompt
    asks for, and the creator can still drag the map afterwards.
    """
    name = (name or '').strip()
    if not name:
        return None
    try:
        response = requests.get(
            PHOTON_URL,
            params={'q': name, 'limit': 1},
            headers={'User-Agent': USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            logger.info('geocode %r: HTTP %s', name, response.status_code)
            return None
        features = response.json().get('features') or []
        if not features:
            logger.info('geocode %r: no result', name)
            return None
        feature = features[0]
        lng, lat = feature['geometry']['coordinates'][:2]
        place_type = (feature.get('properties') or {}).get('type') or ''
        return float(lat), float(lng), ZOOM_BY_TYPE.get(place_type, ZOOM_DEFAULT)
    except Exception as exc:  # noqa: BLE001 - a map lookup must never fail a draft
        logger.info('geocode %r failed: %s: %s', name, type(exc).__name__, exc)
        return None
