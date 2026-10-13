"""Embedding a survey on someone else's site (change embed-surveys, #284).

Two things make a respondent page work inside a third-party `<iframe>`:

1. The framing policy. `check_survey_access` calls `mark_embeddable`, which
   records on the request which ancestors may frame this survey;
   `SurveyEmbedMiddleware` turns that into `Content-Security-Policy:
   frame-ancestors …` and drops `X-Frame-Options`. Everything that is not a
   respondent page keeps `SAMEORIGIN`. The decision/application split mirrors
   `mark_indexing` / `SurveyIndexingMiddleware` and for the same reason: the
   survey is known in access control, the response is not.

2. The cookies. Respondent state lives in the session cookie, and a
   `SameSite=Lax` cookie is never sent from inside a cross-site frame. See
   `CROSS_SITE_COOKIES` in settings and `PartitionedCookieMiddleware`.

Everything else here is small: host-list parsing for the creator's allow-list,
the snippet the Share page and the oEmbed endpoint hand out, and the two
request-header tests that tell a framed respondent from a top-level one.
"""
import re
from urllib.parse import urlencode, urlparse

from urllib.parse import urlsplit

from django.conf import settings
from django.urls import reverse
from django.utils.html import escape

# One DNS label: letters, digits, hyphens, no leading/trailing hyphen, <= 63 chars.
_LABEL = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
_HOST_RE = re.compile(rf'^(?:\*\.)?{_LABEL}(?:\.{_LABEL})*$')
MAX_ALLOWED_HOSTS = 50
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 720
MIN_HEIGHT = 300

# The request header the respondent page adds to its HTMX calls when it is
# framed by another site. Fetch Metadata cannot tell us this on a fetch(): the
# HTMX POST is `Sec-Fetch-Dest: empty` whether or not the document is framed.
FRAMED_HEADER = 'MS-Embedded'


class InvalidHost(ValueError):
    pass


def normalise_allowed_hosts(value):
    """Turn a creator's textarea (or a list) into the stored list of hosts.

    Lower-cases, strips a scheme, port and path the creator may have pasted,
    drops blanks and duplicates, keeps order. Accepts `host` or `*.host`
    (IDNA-encoded). Raises `InvalidHost` naming the first bad entry.
    """
    if isinstance(value, str):
        # One host per line (or comma): a space inside an entry is an error,
        # not a separator, so "not a host" is refused rather than read as three.
        raw_entries = re.split(r'[\r\n,]+', value)
    else:
        raw_entries = list(value or [])
    hosts = []
    for raw in raw_entries:
        entry = (raw or '').strip().lower()
        if not entry:
            continue
        original = entry
        if '://' in entry:
            entry = urlparse(entry).netloc
        entry = entry.split('/', 1)[0].split(':', 1)[0].strip('.')
        try:
            entry = entry.encode('idna').decode('ascii')
        except UnicodeError:
            raise InvalidHost(original)
        if not entry or len(entry) > 253 or not _HOST_RE.match(entry):
            raise InvalidHost(original)
        if entry not in hosts:
            hosts.append(entry)
    if len(hosts) > MAX_ALLOWED_HOSTS:
        raise InvalidHost(hosts[MAX_ALLOWED_HOSTS])
    return hosts


def frame_ancestors(hosts):
    """The value of the `frame-ancestors` directive for an allow-list.

    `'self'` is always there so the editor's Live Preview keeps framing the
    respondent page. Only `https://` ancestors are emitted: a page served over
    HTTP cannot carry a `Secure` cookie, so it could not complete the survey
    anyway.
    """
    if not hosts:
        return '*'
    return ' '.join(["'self'"] + [f'https://{h}' for h in hosts])


def is_framed(request):
    """Is this request a frame navigation from another site?

    `Sec-Fetch-Dest: iframe` alone would also match the editor's Live Preview,
    which frames the respondent page same-origin; `Sec-Fetch-Site` separates
    the two. `embed=1` is the snippet's own marker and covers a browser that
    sends no Fetch Metadata.
    """
    dest = request.headers.get('Sec-Fetch-Dest', '')
    site = request.headers.get('Sec-Fetch-Site', '')
    if dest == 'iframe' and site and site != 'same-origin':
        return True
    return request.GET.get('embed') == '1'


def is_framed_htmx(request):
    """Is this HTMX request issued by a respondent page framed by another site?"""
    return request.headers.get(FRAMED_HEADER) == '1'


def framed_request(request):
    """Framed, whichever way this request reached us: a frame navigation
    (`is_framed`) or an HTMX call from a framed page (`is_framed_htmx`)."""
    return is_framed_htmx(request) or is_framed(request)


def embed_host(request):
    """The host of the page framing us, from the Referer; '' when unknown."""
    try:
        host = (urlparse(request.META.get('HTTP_REFERER', '')).hostname or '').lower()
    except ValueError:
        return ''
    if host.startswith('www.'):
        host = host[4:]
    return host[:253]


def anonymously_openable(survey):
    """Can a visitor with nothing but the link open this survey right now?

    The subset of `check_survey_access` that needs no request: this is what
    the oEmbed endpoint and the discovery link gate on, because a snippet for
    a survey that then 404s inside the frame helps nobody.
    """
    from .content_screening import is_held
    return (
        survey.status == 'published'
        and not survey.has_password()
        and not is_held(survey)
    )


def public_base_url(request):
    """Scheme + host the public reached us on, for URLs that leave the site.

    Behind Cloudflare and Render `request.scheme` is `http` (#248), and a
    snippet or oEmbed payload saying `http://` is worse than a wrong sitemap:
    an https host page refuses to frame it as mixed content and a `Secure`
    cookie never gets set. `SECURE_PROXY_SSL_HEADER` would fix that site-wide
    but also changes `is_secure()` for CSRF, cookies and redirects -- out of
    proportion here. So: the proxy's X-Forwarded-Proto, else SITE_URL's scheme
    when it names this host, else whatever the request says (local dev).
    """
    host = request.get_host()
    forwarded = request.META.get('HTTP_X_FORWARDED_PROTO', '').split(',')[0].strip().lower()
    if forwarded in ('http', 'https'):
        scheme = forwarded
    else:
        site = urlsplit(getattr(settings, 'SITE_URL', '') or '')
        scheme = site.scheme if site.scheme and site.netloc == host else request.scheme
    return f'{scheme}://{host}'


def survey_url(request, survey):
    return public_base_url(request) + reverse('survey', args=[str(survey.uuid)])


def embed_js_url(request):
    return public_base_url(request) + reverse('embed_js')


def oembed_url(request, survey):
    return public_base_url(request) + reverse('oembed') + '?' + urlencode({'url': survey_url(request, survey), 'format': 'json'})


def clamp_size(value, default, floor):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number <= 0:
        return default
    return max(min(number, default), floor)


def snippet_html(request, survey, width=None, height=None, with_script=True):
    """The iframe snippet creators paste, and (without the script) what oEmbed returns.

    `allow="geolocation"` matters: without it the respondent map's "my
    location" is silently refused inside a frame. `embed.js` is what makes a
    form-layout survey grow with its content; a map-layout survey fills
    whatever height the host gives it.

    `with_script=False` is for oEmbed: Iframely (which Notion, Ghost and
    others embed through) drops the whole `html` when it contains a `<script>`
    — on the PR #286 preview it handed Notion an empty string and Notion
    showed "This embed couldn't be loaded". Consumers of oEmbed never run
    scripts anyway, so there the frame keeps its fixed height. The bare
    `width`/`height` attributes are what those parsers read.
    """
    src = survey_url(request, survey) + '?embed=1'
    px_height = int(height or DEFAULT_HEIGHT)
    style_width = f'{int(width)}px' if width else '100%'
    size_attrs = f'width="{int(width)}" ' if width else ''
    size_attrs += f'height="{px_height}" '
    iframe = (
        f'<iframe src="{escape(src)}" title="{escape(survey.name)}" {size_attrs}'
        f'style="width:{style_width};max-width:100%;height:{px_height}px;border:0;" '
        f'allow="geolocation; fullscreen" loading="lazy"></iframe>'
    )
    if not with_script:
        return iframe
    return iframe + f'\n<script async src="{escape(embed_js_url(request))}"></script>'
