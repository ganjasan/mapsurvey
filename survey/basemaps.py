"""One resolver for basemap keys (change map-styles-library, #542; epic #545, ADR 0001).

A basemap key is a preset key (`streets`, `satellite`, `topo`, `paper`, `paper_b`) or
`style:<uuid>` of a workspace `MapStyle`. Every surface that draws a base map — the
Leaflet pages through `partials/basemap_layers.html` and the `{% basemap_table %}` tag,
the print frame through `resolve`, the public results page — asks this module what a key
means for a workspace and renders from the answer. No template holds a Mapbox style id
or tile URL; the tile template is `settings.MAPBOX_TILES_URL`, the style ids are rows.

Pins: a published survey's `basemap_pins` names the version of each workspace style it
shows. `resolve(key, org, pins)` honours a pin that names a ready version and falls back
to the latest ready version otherwise, so a new version never changes a live survey and a
draft (no pins) previews the latest.
"""
from dataclasses import dataclass

from django.conf import settings

from .models import (MAPBOX_ATTRIBUTION, PRESET_BASEMAP_KEYS, STYLE_KEY_PREFIX, MapStyle,
                     MapStyleVersion, PublicResultsBlock, SurveyHeader, SurveySection)

ESRI_WORLD_IMAGERY_URL = ('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/'
                          'MapServer/tile/{z}/{y}/{x}')
ESRI_ATTRIBUTION = '&copy; Esri'
FALLBACK_KEY = 'streets'


@dataclass(frozen=True)
class Basemap:
    key: str
    name: str
    kind: str                 # 'preset' | 'workspace'
    provider: str             # 'mapbox' | 'xyz'
    tile_url: str             # `{accessToken}` left for the client on Mapbox URLs
    tile_size: int
    zoom_offset: int
    max_zoom: int
    attribution: str
    static_style: str         # Mapbox style id for the Static Images API (print)
    style_uuid: str = ''
    version: int | None = None

    @property
    def is_mapbox(self):
        return self.provider == MapStyleVersion.MAPBOX

    def leaflet(self):
        """The entry `partials/basemap_layers.html` builds an `L.tileLayer` from."""
        opts = {'attribution': self.attribution, 'maxZoom': self.max_zoom}
        if self.tile_size != 256:
            opts['tileSize'] = self.tile_size
            opts['zoomOffset'] = self.zoom_offset
        return {'name': self.name, 'url': self.tile_url, 'opts': opts, 'kind': self.kind,
                'provider': self.provider}


def is_style_key(key):
    return isinstance(key, str) and key.startswith(STYLE_KEY_PREFIX)


def style_uuid_of(key):
    return key[len(STYLE_KEY_PREFIX):] if is_style_key(key) else None


def _tile_size_of(url):
    return 512 if '/tiles/512/' in url else 256


def _from_version(style, version):
    if version.provider == MapStyleVersion.MAPBOX:
        url = settings.MAPBOX_TILES_URL.replace('{style}', version.mapbox_style_id)
        size = _tile_size_of(url)
        return Basemap(
            key=style.basemap_key, name=style.name,
            kind='preset' if style.is_preset else 'workspace', provider=version.provider,
            tile_url=url, tile_size=size, zoom_offset=-1 if size == 512 else 0,
            max_zoom=version.max_zoom, attribution=version.attribution,
            static_style=version.print_style,
            style_uuid='' if style.is_preset else str(style.uuid), version=version.number)
    return Basemap(
        key=style.basemap_key, name=style.name,
        kind='preset' if style.is_preset else 'workspace', provider=version.provider,
        tile_url=version.tile_url, tile_size=256, zoom_offset=0,
        max_zoom=version.max_zoom, attribution=version.attribution,
        static_style=version.static_style,
        style_uuid='' if style.is_preset else str(style.uuid), version=version.number)


def _version_for(style, pins):
    """The pinned ready version when the pin names one, else the latest ready version."""
    ready = [v for v in style.versions.all() if v.status == MapStyleVersion.READY]
    if not ready:
        return None
    if pins and not style.is_preset:
        wanted = pins.get(str(style.uuid))
        for version in ready:
            if version.number == wanted:
                return version
    return max(ready, key=lambda v: v.number)


def _styles_for(org):
    """Preset rows in their fixed order, then the workspace's live styles by name."""
    presets = {s.key: s for s in MapStyle.objects.filter(organization__isnull=True)
               .prefetch_related('versions')}
    ordered = [presets[k] for k in PRESET_BASEMAP_KEYS if k in presets]
    if org is not None:
        ordered.extend(MapStyle.objects.filter(organization=org, archived_at__isnull=True)
                       .prefetch_related('versions').order_by('name', 'pk'))
    return ordered


def available_for(org, pins=None):
    """Every Basemap the workspace can use right now: presets, then its styles with a ready version."""
    out = []
    for style in _styles_for(org):
        version = _version_for(style, pins)
        if version is not None:
            out.append(_from_version(style, version))
    return out


def table_for(org, pins=None):
    """`{key: leaflet entry}` for the templates, in picker order."""
    return {b.key: b.leaflet() for b in available_for(org, pins)}


def choices_for(org):
    """`[(key, name), ...]` for forms and selects."""
    return [(b.key, b.name) for b in available_for(org)]


def resolve(key, org, pins=None):
    """The Basemap a key means for a workspace, or None."""
    if not key:
        return None
    if is_style_key(key):
        style = (MapStyle.objects.filter(uuid=style_uuid_of(key), organization=org, archived_at__isnull=True)
                 .prefetch_related('versions').first()) if org is not None else None
    else:
        style = MapStyle.objects.filter(organization__isnull=True, key=key).prefetch_related('versions').first()
    if style is None:
        return None
    version = _version_for(style, pins)
    return _from_version(style, version) if version is not None else None


def is_valid_key(key, org):
    return resolve(key, org) is not None


def name_of(key, org):
    basemap = resolve(key, org)
    return basemap.name if basemap else key


def first_available(keys, org, pins=None):
    """The first of `keys` the workspace resolves, else the fallback preset's key."""
    for key in keys or []:
        if resolve(key, org, pins) is not None:
            return key
    return FALLBACK_KEY


def referenced_style_uuids(survey):
    """UUIDs of the workspace styles a survey names anywhere: header, sections, results blocks."""
    keys = set(survey.basemaps or [])
    if survey.default_basemap:
        keys.add(survey.default_basemap)
    keys.update(SurveySection.objects.filter(survey_header=survey)
                .exclude(override_basemap__isnull=True).exclude(override_basemap='')
                .values_list('override_basemap', flat=True))
    keys.update(PublicResultsBlock.objects.filter(page__survey=survey).values_list('basemap', flat=True))
    return {style_uuid_of(k) for k in keys if is_style_key(k)}


def pin_latest(survey):
    """Set `survey.basemap_pins` to the latest ready version of every style it names.
    Does not save; the caller is inside its own transaction."""
    pins = {}
    uuids = referenced_style_uuids(survey)
    if uuids:
        for style in MapStyle.objects.filter(uuid__in=uuids, organization=survey.organization).prefetch_related('versions'):
            version = _version_for(style, None)
            if version is not None:
                pins[str(style.uuid)] = version.number
    survey.basemap_pins = pins
    return pins


def usage(org):
    """`{style uuid: number of surveys}` over the workspace's surveys (every version), counting
    a survey once however many places name the style."""
    counts = {}
    headers = SurveyHeader.objects.filter(organization=org, deleted_at__isnull=True)
    for survey in headers.only('pk', 'basemaps', 'default_basemap', 'organization_id'):
        for uuid in referenced_style_uuids(survey):
            counts[uuid] = counts.get(uuid, 0) + 1
    return counts


def surveys_using(style, limit=5):
    """Names of up to `limit` canonical surveys that reference `style` (for a refused delete)."""
    names, seen = [], set()
    headers = (SurveyHeader.objects.filter(organization=style.organization, deleted_at__isnull=True)
               .order_by('-is_canonical', 'name'))
    for survey in headers.only('pk', 'name', 'basemaps', 'default_basemap', 'organization_id', 'is_canonical'):
        if str(style.uuid) in referenced_style_uuids(survey) and survey.name not in seen:
            seen.add(survey.name)
            names.append(survey.name)
            if len(names) >= limit:
                break
    return names
