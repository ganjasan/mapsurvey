"""Settings → a style MapLibre GL can render in the editor (change map-styles-editor, #543).

The editor page is the one place MapLibre runs (ADR 0001): the generator builds the
Mapbox GL style, and `for_maplibre` rewrites what MapLibre cannot read — `mapbox://`
glyphs, sprite and tile sources become `https://api.mapbox.com/...` URLs carrying the
PUBLIC token (the browser would send it anyway), and Mapbox-GL-only keys go. The base
style is fetched with the public token (styles:read is on it) and cached a day under the
same key the publishing task uses, so an editing session and a Save start from one base.
"""
from django.conf import settings as django_settings
from django.core.cache import cache

from .generator import DEFAULT_BASE, MapboxApiError, MapboxStylesClient, apply_settings
from .tasks import BASE_CACHE_TTL

MAPBOX_ONLY_KEYS = ('fog', 'projection', 'imports', 'schema', 'camera', 'lights', 'terrain', 'center', 'zoom',
                    'bearing', 'pitch')
API = 'https://api.mapbox.com'


class PreviewUnavailable(Exception):
    """The base style could not be fetched; the page says so instead of a broken map."""


def _https(url, token):
    if url.startswith('mapbox://fonts/'):
        return f'{API}/fonts/v1/{url[len("mapbox://fonts/"):]}?access_token={token}'
    if url.startswith('mapbox://sprites/'):
        return f'{API}/styles/v1/{url[len("mapbox://sprites/"):]}/sprite?access_token={token}'
    if url.startswith('mapbox://'):
        return f'{API}/v4/{url[len("mapbox://"):]}.json?secure&access_token={token}'
    return url


def for_maplibre(style, token):
    """A copy of `style` MapLibre renders: https sources with the token, no Mapbox-only keys."""
    out = {k: v for k, v in style.items() if k not in MAPBOX_ONLY_KEYS}
    if out.get('glyphs'):
        out['glyphs'] = _https(out['glyphs'], token)
    # The base's sprite, not the style's own (a workspace style has none until published).
    out['sprite'] = _https(f'mapbox://sprites/{DEFAULT_BASE}', token)
    out['sources'] = {name: dict(src, url=_https(src['url'], token)) if 'url' in src else dict(src)
                      for name, src in (style.get('sources') or {}).items()}
    return out


def base_style(base_id=DEFAULT_BASE):
    key = f'map_styles:base:{base_id}'
    cached = cache.get(key)
    if cached is None:
        token = django_settings.MAPBOX_ACCESS_TOKEN
        try:
            cached = MapboxStylesClient(token, django_settings.MAPBOX_ACCOUNT).get_style(base_id)
        except (MapboxApiError, ValueError, OSError) as error:
            raise PreviewUnavailable(str(error)) from error
        cache.set(key, cached, BASE_CACHE_TTL)
    return cached


def maplibre_style(settings, base_id=DEFAULT_BASE):
    style = apply_settings(base_style(base_id), dict(settings, name='preview'))
    return for_maplibre(style, django_settings.MAPBOX_ACCESS_TOKEN)
