"""Template tags for respondent pages inside another site's frame (change embed-surveys).

Safari and every browser on iOS keep no cookies in a third-party frame, so a
framed page carries its own session key: a `<meta>` the page's HTMX calls and
uploads read, and a hidden field in the two full-page forms (language picker,
password gate). `EmbedSessionMiddleware` is the other half.
"""
from django import template
from django.utils.html import format_html

from ..embedding import is_framed

register = template.Library()


def carried_session_key(request):
    """The session key a framed page must carry itself, or ''.

    Only on a page inside another site's frame (or one already reached
    through a carrier), only for an anonymous session. The session is saved
    here if it has no key yet: the key must exist before the page that
    carries it is rendered.
    """
    if request is None:
        return ''
    if not (getattr(request, 'ms_session_carried', False) or is_framed(request)):
        return ''
    session = getattr(request, 'session', None)
    if session is None or session.get('_auth_user_id'):
        return ''
    if not session.session_key:
        session.save()
    return session.session_key or ''


@register.simple_tag(takes_context=True)
def embed_session_meta(context):
    key = carried_session_key(context.get('request'))
    return format_html('<meta name="ms-embed-session" content="{}">', key) if key else ''


@register.simple_tag(takes_context=True)
def embed_session_field(context):
    key = carried_session_key(context.get('request'))
    return format_html('<input type="hidden" name="ms_sid" value="{}">', key) if key else ''
