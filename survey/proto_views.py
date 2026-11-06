"""PROTOTYPE ONLY (change map-styles-rendering-path, #541) — never merged.

Serves a map style built by scripts/mapbox_style_publish.py as MapLibre-readable JSON:
mapbox:// URLs rewritten to https with the public token, Mapbox-GL-only keys dropped.
Mounted only under DEBUG.
"""
import importlib.util
import json
import os

from django.conf import settings
from django.http import Http404, JsonResponse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('mapbox_style_publish', os.path.join(REPO, 'scripts', 'mapbox_style_publish.py'))
publish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publish)


def _https(url, token):
    if url.startswith('mapbox://fonts/'):
        return 'https://api.mapbox.com/fonts/v1/' + url[len('mapbox://fonts/'):] + f'?access_token={token}'
    if url.startswith('mapbox://sprites/'):
        return 'https://api.mapbox.com/styles/v1/' + url[len('mapbox://sprites/'):] + f'/sprite?access_token={token}'
    if url.startswith('mapbox://'):
        return f'https://api.mapbox.com/v4/{url[len("mapbox://"):]}.json?secure&access_token={token}'
    return url


def proto_style(request, name):
    if not settings.DEBUG:
        raise Http404
    path = os.path.join(REPO, 'scripts', 'map_styles', f'{name}.json')
    if not os.path.exists(path):
        raise Http404
    with open(os.path.join(REPO, 'survey', 'tests', 'fixtures', 'mapbox_streets_v12.json')) as fh:
        base = json.load(fh)
    with open(path) as fh:
        style = publish.apply_settings(base, json.load(fh))
    token = settings.MAPBOX_ACCESS_TOKEN
    for key in ('fog', 'projection', 'imports', 'schema', 'camera', 'lights', 'terrain', 'center', 'zoom'):
        style.pop(key, None)
    style['glyphs'] = _https(style['glyphs'], token)
    style['sprite'] = _https('mapbox://sprites/mapbox/streets-v12', token)
    for source in style['sources'].values():
        if 'url' in source:
            source['url'] = _https(source['url'], token)
    return JsonResponse(style)
