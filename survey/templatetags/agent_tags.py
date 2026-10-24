"""Drawing the agent page's step strings (change agent-onboarding).

A step is translated plain text. Two marks survive translation untouched:
`[[Name]]` is a button or menu the reader looks for on the vendor's screen,
drawn as a key, and `{url}` is the server address, drawn as a field with a Copy
button. Everything else is escaped -- translators never write HTML.
"""
import re

from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

register = template.Library()

_KEY = re.compile(r'\[\[(.+?)\]\]')


@register.simple_tag
def agent_step(text, server_url):
    html = escape(str(text))
    html = _KEY.sub(lambda m: '<span class="ag-key">%s</span>' % m.group(1), html)
    if '{url}' in html:
        field = format_html(
            '<span class="ag-copy"><code>{}</code>'
            '<button type="button" class="btn btn-sm btn-outline-secondary" data-copy="{}">'
            '<i class="far fa-copy"></i> {}</button></span>',
            server_url, server_url, _('Copy'),
        )
        html = html.replace('{url}', field)
    return mark_safe(html)
