"""`{% basemap_table org pins %}` — the provider table a map surface builds its base layers
from (change map-styles-library, #542). One JSON object `{key: {name, url, opts, kind,
provider}}` in picker order: presets, then the workspace's ready styles. `pins` is a
published survey's `basemap_pins`; pass `None` for a draft or a creator surface. The tag
is the only way a template learns a tile URL — see survey/basemaps.py."""
import json

from django import template
from django.utils.safestring import mark_safe

from survey import basemaps

register = template.Library()


@register.simple_tag
def basemap_table(org, pins=None):
    return mark_safe(json.dumps(basemaps.table_for(org, pins or None)))


@register.simple_tag
def basemap_name(key, org):
    return basemaps.name_of(key, org)
