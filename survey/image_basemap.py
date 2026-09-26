"""Image basemaps: a creator's own picture as the survey's map (change `custom-image-basemap`).

The picture is NOT georeferenced. It sits on a fixed rectangle centred on 0°, 0°
whose longer side spans IMAGE_SPAN_DEG degrees, in the map's ordinary EPSG:3857
CRS. At that latitude Mercator's scale error is far below anything visible, so
shapes drawn on the picture keep their shape, and answers stay plain SRID 4326
geometry — every consumer (shared map, layers, Responses, export) works
unchanged. The bounds come from here and only from here; the browser never
recomputes them (`ImageBasemap.apply` in js/image_basemap.js draws what
`config_for` hands it).

Draft copies and versions copy the image fields like `basemaps`, so several
SurveyHeader rows can name one stored file. Delete through
`delete_if_unreferenced`, never `image_basemap.delete()` directly.
"""
import io

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _

IMAGE_SPAN_DEG = 1.0

ALLOWED_CONTENT_TYPES = ('image/png', 'image/jpeg', 'image/webp')


def max_upload_bytes():
    return getattr(settings, 'IMAGE_BASEMAP_MAX_UPLOAD_BYTES', 20 * 1024 * 1024)


def max_pixels():
    return getattr(settings, 'IMAGE_BASEMAP_MAX_PIXELS', 64_000_000)


def max_side():
    return getattr(settings, 'IMAGE_BASEMAP_MAX_SIDE', 8192)


def bounds_for(width, height):
    """[[south, west], [north, east]] of a width × height picture."""
    width, height = float(width), float(height)
    if width >= height:
        half_w = IMAGE_SPAN_DEG / 2
        half_h = half_w * height / width
    else:
        half_h = IMAGE_SPAN_DEG / 2
        half_w = half_h * width / height
    return [[-half_h, -half_w], [half_h, half_w]]


def config_for(survey):
    """What every map surface needs to draw the image, or None on a tiles survey."""
    if survey is None or not survey.uses_image_basemap:
        return None
    return {
        'url': survey.image_basemap.url,
        'bounds': bounds_for(survey.image_basemap_width, survey.image_basemap_height),
        'width': survey.image_basemap_width,
        'height': survey.image_basemap_height,
    }


def point_inside(survey, point):
    """True if `point` (a GEOS Point or None) lies on the survey's picture."""
    if point is None or not survey.uses_image_basemap:
        return False
    (south, west), (north, east) = bounds_for(survey.image_basemap_width, survey.image_basemap_height)
    return south <= point.y <= north and west <= point.x <= east


def section_map_view(survey, section):
    """The map settings a respondent section applies, with the real-world ones
    neutralised on an image survey: a start position off the picture is
    dropped (the view stays / fits the picture), geolocation is never asked
    for and the tile override is ignored. Stored values are untouched, so they
    apply again if the creator switches back to tiles."""
    pos, zoom = section.start_map_postion, section.start_map_zoom
    if not survey.uses_image_basemap:
        return {'position': pos, 'zoom': zoom,
                'use_geolocation': section.use_geolocation,
                'basemap': section.override_basemap or ''}
    inside = point_inside(survey, pos)
    return {'position': pos if inside else None, 'zoom': zoom if inside else None,
            'use_geolocation': False, 'basemap': ''}


FIELDS = ('basemap_mode', 'image_basemap', 'image_basemap_width', 'image_basemap_height')


def copy_fields(src):
    """Kwargs that give a new header the same picture (shared file name).
    Processing state is not copied: a pending upload belongs to `src`.

    The picture goes across as its NAME, never as src's FieldFile: Django's file
    descriptor re-points a foreign FieldFile at the instance it is assigned to,
    so both rows would share one object and a replacement in one would rename
    the other in memory."""
    fields = {f: getattr(src, f) for f in FIELDS}
    fields['image_basemap'] = src.image_basemap.name if src.image_basemap else None
    return fields


def is_referenced(name, exclude_pk=None):
    from .models import SurveyHeader
    qs = SurveyHeader.objects.filter(image_basemap=name)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def delete_if_unreferenced(name, exclude_pk=None):
    """Delete a stored picture unless another header (other than `exclude_pk`,
    the one letting go of it) still names it."""
    if not name or is_referenced(name, exclude_pk=exclude_pk):
        return False
    from .models import SurveyHeader
    SurveyHeader._meta.get_field('image_basemap').storage.delete(name)
    return True


def raw_storage():
    from .models import _private_media_storage
    return _private_media_storage()


def store_raw_upload(uploaded):
    """Stream an unvalidated upload to the PRIVATE tier under a random key and
    return the key. It is never readable at a public URL; the task deletes it."""
    import uuid
    return raw_storage().save(f'basemap_uploads/{uuid.uuid4().hex}', uploaded)


def header_size(uploaded):
    """(width, height) from the file header, or None. Pillow's open() is lazy:
    it reads the header and allocates no pixels, so this is safe in a web
    request where decoding is not."""
    from PIL import Image
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as img:
            size = img.size
        return size
    except Exception:
        return None
    finally:
        uploaded.seek(0)


class ImageRejected(Exception):
    """An upload that is not a picture we can show. `str()` is creator-facing."""


def process_file(fileobj):
    """Decode, bound, orient and re-encode an untrusted picture.

    Returns (webp_bytes, width, height). Runs on the Celery worker (and inside
    the ZIP import, which is also on the worker) — never in a web request: a
    worker keeps the RSS of its largest request for life, and a large picture
    decodes to hundreds of MB. The pixel cap is checked from the header BEFORE
    any pixel is allocated, which is what defeats a decompression bomb.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    limit = max_pixels()
    try:
        head = Image.open(fileobj)
        width, height = head.size
        if head.format not in ('PNG', 'JPEG', 'WEBP'):
            raise ImageRejected(_('The file is not a PNG, JPEG or WebP image.'))
        if width * height > limit:
            raise ImageRejected(_('The image is %(w)d × %(h)d pixels; the limit is %(mp)d megapixels.') % {
                'w': width, 'h': height, 'mp': limit // 1_000_000})
        head.verify()
        fileobj.seek(0)
        # verify() leaves the object unusable; reopen for decoding. The bomb
        # guard is Pillow's own as well, so a lying header still stops here.
        old_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = limit
        try:
            img = Image.open(fileobj)
            img.load()
        finally:
            Image.MAX_IMAGE_PIXELS = old_limit
    except ImageRejected:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning,
            OSError, SyntaxError, ValueError):
        raise ImageRejected(_('The file is not a PNG, JPEG or WebP image we can read.'))

    img = ImageOps.exif_transpose(img)
    img = img.convert('RGBA' if img.mode in ('RGBA', 'LA', 'P') and _has_alpha(img) else 'RGB')
    side = max_side()
    if max(img.size) > side:
        img.thumbnail((side, side), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, 'WEBP', quality=85, method=4)
    return out.getvalue(), img.size[0], img.size[1]


def _has_alpha(img):
    if img.mode in ('RGBA', 'LA'):
        return True
    return img.mode == 'P' and 'transparency' in img.info


def store_processed(survey, webp_bytes, width, height, activate=False):
    """Point `survey` at a freshly processed picture and let go of the old one.
    `activate` also switches the survey to it (a creator's upload, design D9);
    ZIP import leaves it off and keeps the archive's own mode."""
    old = survey.image_basemap.name if survey.image_basemap else ''
    survey.image_basemap.save('basemap.webp', ContentFile(webp_bytes), save=False)
    survey.image_basemap_width = width
    survey.image_basemap_height = height
    survey.image_basemap_state = ''
    survey.image_basemap_error = ''
    survey.image_basemap_pending = ''
    fields = [
        'image_basemap', 'image_basemap_width', 'image_basemap_height',
        'image_basemap_state', 'image_basemap_error', 'image_basemap_pending', 'updated_at',
    ]
    if activate:
        survey.basemap_mode = 'image'
        fields.append('basemap_mode')
    survey.save(update_fields=fields)
    if old and old != survey.image_basemap.name:
        delete_if_unreferenced(old, exclude_pk=survey.pk)


def clear(survey):
    """Forget the picture (and switch back to tiles)."""
    old = survey.image_basemap.name if survey.image_basemap else ''
    survey.image_basemap = None
    survey.image_basemap_width = None
    survey.image_basemap_height = None
    survey.image_basemap_state = ''
    survey.image_basemap_error = ''
    survey.image_basemap_pending = ''
    survey.basemap_mode = 'tiles'
    survey.save()
    if old:
        delete_if_unreferenced(old, exclude_pk=survey.pk)


def aspect_differs(old_w, old_h, new_w, new_h, tolerance=0.01):
    if not (old_w and old_h and new_w and new_h):
        return False
    return abs((old_w / old_h) / (new_w / new_h) - 1) > tolerance


def family_has_geo_answers(survey):
    from django.db.models import Q
    from .models import Answer
    from .versioning import family_ids_with_draft
    return Answer.objects.filter(
        survey_session__survey_id__in=family_ids_with_draft(survey),
    ).filter(Q(point__isnull=False) | Q(line__isnull=False) | Q(polygon__isnull=False)).exists()


def geojson_member(survey, image_name='basemap.webp'):
    """Foreign member added to every GeoJSON of an image survey's data export."""
    return {
        'image': image_name,
        'bounds': bounds_for(survey.image_basemap_width, survey.image_basemap_height),
        'note': ('Coordinates are positions on the survey\'s uploaded image, not on Earth. '
                 'Place the image with these bounds ([[south, west], [north, east]], degrees) '
                 'to see the features where respondents drew them.'),
    }
