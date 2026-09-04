"""Attachments on layer objects: validation, embeds and the card payload.

Creator-side counterpart of `survey/uploads.py`. Files land on the PUBLIC tier
(respondents load them unauthenticated in <img>/<audio>/<video>), so the
allow-lists here are stricter than the respondent ones where it matters — no
SVG, no HTML-ish documents — and the embed path accepts exactly two hosts.
"""
import re
from urllib.parse import urlparse, parse_qs

from django.utils.translation import gettext_lazy as _

from .uploads import ALLOWED_TYPES as _RESPONDENT_TYPES, _MAGIC, PLATFORM_MAX_BYTES
from .html_sanitize import coerce_creator_html

MAX_ASSET_BYTES = PLATFORM_MAX_BYTES          # 25 MB, same constant as respondent uploads
MAX_ASSETS_PER_OBJECT = 10
MAX_ASSET_BYTES_PER_LAYER = 200 * 1024 * 1024

ALLOWED_ASSET_TYPES = {
    'image': {'image/jpeg', 'image/png', 'image/webp', 'image/gif'},
    'audio': set(_RESPONDENT_TYPES['audio']),
    'document': set(_RESPONDENT_TYPES['document']) - {'text/plain', 'text/csv'},
    'video': {'video/mp4', 'video/webm', 'video/quicktime'},
}

EMBED_HOSTS = ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
               'vimeo.com', 'www.vimeo.com', 'player.vimeo.com')


class AssetRejected(Exception):
    """Creator-readable refusal."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


def kind_for_content_type(content_type):
    for kind, allowed in ALLOWED_ASSET_TYPES.items():
        if content_type in allowed:
            return kind
    return None


def validate_asset_upload(obj, uploaded_file):
    """Return (kind, content_type) or raise AssetRejected. Enforces the per-file,
    per-object and per-layer caps and the magic-byte check where reliable."""
    from django.db.models import Sum
    from .models import LayerObjectAsset

    content_type = (uploaded_file.content_type or '').lower().split(';')[0].strip()
    kind = kind_for_content_type(content_type)
    if kind is None:
        raise AssetRejected(_('This file type is not accepted. Use an image, audio, PDF/Office document or MP4/WebM video.'))
    if uploaded_file.size > MAX_ASSET_BYTES:
        raise AssetRejected(_('The file is too large (limit %(mb)s MB). Larger videos can be embedded by link.')
                            % {'mb': MAX_ASSET_BYTES // (1024 * 1024)})
    signatures = _MAGIC.get(content_type)
    if signatures:
        head = uploaded_file.read(16)
        uploaded_file.seek(0)
        if not any(head.startswith(sig) for sig in signatures):
            raise AssetRejected(_('The file does not match its declared type.'))
        if content_type == 'image/webp' and head[8:12] != b'WEBP':
            raise AssetRejected(_('The file does not match its declared type.'))

    if obj.assets.count() >= MAX_ASSETS_PER_OBJECT:
        raise AssetRejected(_('An object can carry at most %(n)s attachments.') % {'n': MAX_ASSETS_PER_OBJECT})
    used = (LayerObjectAsset.objects.filter(object__layer=obj.layer)
            .aggregate(s=Sum('size_bytes'))['s'] or 0)
    if used + uploaded_file.size > MAX_ASSET_BYTES_PER_LAYER:
        raise AssetRejected(_('This layer\'s attachments would exceed %(mb)s MB.')
                            % {'mb': MAX_ASSET_BYTES_PER_LAYER // (1024 * 1024)})
    return kind, content_type


_YT_ID = re.compile(r'^[A-Za-z0-9_-]{6,20}$')
_VIMEO_ID = re.compile(r'^\d{5,15}$')


def normalize_embed_url(url):
    """Turn a YouTube / Vimeo page URL into the player URL we will iframe, or
    raise AssetRejected. Only these two hosts: an <iframe src> is a script
    surface, and the sanitizer's `iframe` allowance is only safe because the
    host is pinned here."""
    parsed = urlparse((url or '').strip())
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in EMBED_HOSTS:
        raise AssetRejected(_('Only YouTube and Vimeo links can be embedded.'))
    host = parsed.hostname
    video_id = ''
    if host == 'youtu.be':
        video_id = parsed.path.strip('/').split('/')[0]
    elif 'youtube' in host:
        if parsed.path.startswith('/embed/') or parsed.path.startswith('/shorts/'):
            video_id = parsed.path.split('/')[2] if len(parsed.path.split('/')) > 2 else ''
        else:
            video_id = (parse_qs(parsed.query).get('v') or [''])[0]
        if not _YT_ID.match(video_id):
            raise AssetRejected(_('That does not look like a YouTube video link.'))
        return f'https://www.youtube.com/embed/{video_id}'
    if host == 'youtu.be':
        if not _YT_ID.match(video_id):
            raise AssetRejected(_('That does not look like a YouTube video link.'))
        return f'https://www.youtube.com/embed/{video_id}'
    # vimeo
    parts = [p for p in parsed.path.split('/') if p]
    video_id = next((p for p in reversed(parts) if _VIMEO_ID.match(p)), '')
    if not video_id:
        raise AssetRejected(_('That does not look like a Vimeo video link.'))
    return f'https://player.vimeo.com/video/{video_id}'


def object_card_payload(obj):
    """What the respondent popup (and the editor preview) render for one object."""
    assets = []
    cover = ''
    for asset in obj.assets.all():
        url = asset.url
        if asset.kind == 'image' and not cover:
            cover = url
        assets.append({
            'id': asset.pk, 'kind': asset.kind, 'url': url,
            'title': asset.title, 'content_type': asset.content_type,
        })
    return {
        'key': obj.key,
        'title': obj.title,
        'category': obj.category,
        'description': coerce_creator_html(obj.description or ''),
        'link': obj.link,
        'cover': cover,
        'assets': assets,
    }
