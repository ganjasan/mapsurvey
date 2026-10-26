"""JSON-LD about the Mapsurvey brand for marketing pages (change brand-entity, #443).

The nodes come from `survey/brand.py`; these tags only serialise them. `<`, `>` and `&` are written
as unicode escapes so no value can end the `<script>` element early.
"""
import json

from django import template
from django.utils.safestring import mark_safe

from .. import brand

register = template.Library()

_ESCAPES = {ord("<"): "\\u003c", ord(">"): "\\u003e", ord("&"): "\\u0026"}


def _script(*nodes):
    """One <script> per node: each is a standalone document, linked to the others by @id."""
    out = []
    for node in nodes:
        payload = json.dumps({"@context": "https://schema.org", **node}, ensure_ascii=False, indent=1)
        out.append(f'<script type="application/ld+json">\n{payload.translate(_ESCAPES)}\n</script>')
    return mark_safe("\n".join(out))


@register.simple_tag
def brand_jsonld():
    """Organization + SoftwareApplication, on every page that extends base_landing.html."""
    return _script(brand.organization(), brand.software())


@register.simple_tag
def website_jsonld():
    """WebSite (the site name Google shows), on the homepage pair only."""
    return _script(brand.website())
