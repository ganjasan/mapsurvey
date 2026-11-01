"""The code off a photographed page (spec paper-photo-entry, design D3) — locally,
never by a model.

`zxing-cpp` decodes the page's QR (`MSFORM:<form>:<copy>:<page>:<pages>`, two of
them, bottom corners, error level H). Ingest calls `decode` on the photo at FULL
resolution, before it is shrunk for storage, so a 20 mm QR on a 12 MP phone shot
has ~30 px per module to work with; the recognition task tries again on the
stored JPEG for a page that arrived without one. A page whose code will not read
is set aside for the operator — guessing its page from the model would put a
respondent's answers into another respondent's response.
"""
import io
import logging

from survey.print import form_code

logger = logging.getLogger('survey.paper')

# A huge noisy photo sometimes defeats the detector where a smaller copy does not.
_RETRY_SIDE = 1800


def _read(img):
    import zxingcpp
    try:
        results = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
    except Exception:  # noqa: BLE001 — a decoder hiccup is "no code", not a crash
        return None
    for r in results:
        code = form_code.parse(r.text)
        if code is not None:
            return code
    return None


def decode(img):
    """A `form_code.Code` from a Pillow image, or None."""
    code = _read(img)
    if code is not None:
        return code
    w, h = img.size
    if max(w, h) > _RETRY_SIDE:
        scale = _RETRY_SIDE / max(w, h)
        small = img.resize((max(1, round(w * scale)), max(1, round(h * scale))))
        code = _read(small)
        if code is not None:
            return code
        img, (w, h) = small, small.size
    # The QRs sit in the bottom corners; a phone shot taken at an angle shrinks
    # them. Try each bottom quarter at 2x, then the top ones (a page upside down).
    cw, ch = w // 2, h // 3
    for box in ((0, h - ch, cw, h), (w - cw, h - ch, w, h), (0, 0, cw, ch), (w - cw, 0, w, ch)):
        code = _read(img.crop(box).resize((cw * 2, ch * 2)))
        if code is not None:
            return code
    return None


def decode_jpeg(jpeg_bytes):
    from PIL import Image
    with Image.open(io.BytesIO(jpeg_bytes)) as img:
        img.load()
        return decode(img)


def is_first_page_link(text, survey_uuid):
    """The page-1 "answer online" QR of a printed form of this survey:
    `…/surveys/<uuid>/?utm_source=paper&utm_medium=print_form` (`pdf._tracked_link`)."""
    from urllib.parse import parse_qs, urlsplit
    try:
        parts = urlsplit(text or '')
    except ValueError:
        return False
    if parts.path.rstrip('/') != f'/surveys/{survey_uuid}':
        return False
    query = parse_qs(parts.query)
    return query.get('utm_source') == ['paper'] and query.get('utm_medium') == ['print_form']


def shows_first_page_link(jpeg_bytes, survey_uuid):
    """True when the photo carries the page-1 online-link QR of this survey.

    Only page 1 prints it, so a photo whose form code is out of frame (a form
    printed before the two corner QRs, or cropped) is still page 1 — of the
    response it was dropped into; the link names the survey, not the copy."""
    import zxingcpp
    from PIL import Image
    with Image.open(io.BytesIO(jpeg_bytes)) as img:
        img.load()
        try:
            results = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
        except Exception:  # noqa: BLE001 — a decoder hiccup is "no link"
            return False
    return any(is_first_page_link(r.text, survey_uuid) for r in results)
