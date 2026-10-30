"""One upload → page images, in the worker (spec paper-photo-entry, design D2).

Everything here decodes pixels, so nothing here may run in a web request: a
gunicorn worker keeps the RSS of its largest request for life (2026-09-15), and
a 12 MP photo is ~50 MB decoded. The worker handles one page at a time and
drops it before the next; the original upload is deleted once its pages exist.
"""
import io
import logging

from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger('survey.paper')

# Long side of a stored page. 2200 px gives a 16 mm QR on A4 ~120 px (the
# decoder wants ≥ 2 px per module, a version-3 QR has 29) and keeps a page at
# ~500 KB — what the browser shows, the decoder reads and the model receives.
MAX_SIDE = 2200
JPEG_QUALITY = 85
PDF_DPI = 150

KIND_PDF = 'pdf'
KIND_IMAGE = 'image'


class NotADocument(Exception):
    """The bytes are neither an image we read nor a PDF."""


def sniff(head):
    """`pdf` | `image` | None from the first bytes of a file (never the name)."""
    if head.startswith(b'%PDF'):
        return KIND_PDF
    if head.startswith(b'\xff\xd8\xff'):                     # JPEG
        return KIND_IMAGE
    if head.startswith(b'\x89PNG\r\n\x1a\n'):                 # PNG
        return KIND_IMAGE
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':         # WEBP
        return KIND_IMAGE
    if head[4:8] == b'ftyp' and head[8:12] in (b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis',
                                               b'mif1', b'msf1', b'avif'):
        return KIND_IMAGE                                     # HEIC/HEIF/AVIF
    return None


def _normalise(img):
    """EXIF-upright RGB JPEG bytes with the long side ≤ MAX_SIDE; (bytes, w, h)."""
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    w, h = img.size
    scale = MAX_SIDE / max(w, h)
    if scale < 1:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), img.size[0], img.size[1]


def iter_pages(data, kind):
    """Yield (jpeg_bytes, width, height) per page of an upload's bytes."""
    if kind == KIND_PDF:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    bitmap = page.render(scale=PDF_DPI / 72)
                    img = bitmap.to_pil()
                finally:
                    page.close()
                yield _normalise(img)
                del img
        finally:
            pdf.close()
        return
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        yield _normalise(img)


def ingest_upload(upload):
    """Split `upload` into PaperPage rows; returns the number of pages.

    Idempotent: a row past `queued` is left alone (a redelivered message must
    not create the pages twice). A file that is not a photo or PDF is marked
    `failed` with the message the list shows; a decoder crash is marked failed
    with a generic message and re-raised for the error reporter.
    """
    from survey.models import PaperPage

    if upload.status != 'queued':
        return upload.pages_count
    batch = upload.batch
    try:
        with upload.file.open('rb') as fh:
            data = fh.read()
    except Exception:  # noqa: BLE001 — a missing object is an outcome, not a crash
        _fail(upload, 'The file could not be read.')
        return 0
    kind = sniff(data[:16])
    if kind is None:
        _fail(upload, 'Not a photo or PDF')
        return 0
    created = 0
    try:
        for jpeg, width, height in iter_pages(data, kind):
            seq = _next_page_seq(batch)
            page = PaperPage(batch=batch, upload=upload, seq=seq, width=width, height=height)
            page.image.save(f'{seq}.jpg', ContentFile(jpeg), save=False)
            page.save()
            created += 1
            del jpeg
    except Exception:
        upload.pages_count = created
        _fail(upload, 'The file could not be opened. The error has been reported.')
        raise
    finally:
        del data
    upload.status = 'split'
    upload.pages_count = created
    upload.finished_at = timezone.now()
    upload.discard_file()
    upload.save()
    batch.touch()
    return created


def _fail(upload, message):
    upload.status = 'failed'
    upload.error = message
    upload.finished_at = timezone.now()
    upload.discard_file()
    upload.save()


def _next_page_seq(batch):
    """Hand out the batch's next page number under a row lock: uploads of one
    batch are split by several workers at once."""
    from django.db import transaction
    from survey.models import PaperBatch
    with transaction.atomic():
        locked = PaperBatch.objects.select_for_update().get(pk=batch.pk)
        seq = locked.next_page_seq
        locked.next_page_seq = seq + 1
        locked.save(update_fields=['next_page_seq'])
    return seq
