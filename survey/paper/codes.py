"""The form code off a photographed page (spec paper-photo-entry, design D3).

Locally first: `zxing-cpp` decodes the footer QR (`ms:form:<form>:<page>:<pages>`)
over the normalised page and, when a skewed phone shot hides it, over an
upscale of the corners. Only when no QR reads does the model get a small call to
read the footer text `MS-<form>-<page>` — `form_code.parse` tolerates the 0/O
and 1/I confusions a model makes as readily as a clerk. `code_source` records
which way the code came, so PostHog can say how often the fallback runs.
"""
import io
import logging

from survey.print import form_code

logger = logging.getLogger('survey.paper')

CODE_SCHEMA = {
    'type': 'object',
    'properties': {
        'code': {'type': 'string', 'description': 'The form code printed in the page footer, e.g. MS-7K-3, or an empty string'},
    },
    'required': ['code'],
    'additionalProperties': False,
}

CODE_SYSTEM = (
    'You read the footer of a photographed paper form. The footer carries a short code '
    'starting with "MS-", a dash, letters and digits, a dash and a page number, e.g. MS-7K-3. '
    'Return exactly that code as printed. If no such code is visible, return an empty string. '
    'Never invent a code.'
)
CODE_USER = 'Read the form code in the footer of this page.'


def _decode_all(img):
    import zxingcpp
    results = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
    return [r.text for r in results if r.text]


def decode_qr(jpeg_bytes):
    """(form_id, page, pages) from the page's QR, or None."""
    from PIL import Image
    with Image.open(io.BytesIO(jpeg_bytes)) as img:
        img.load()
        texts = _decode_all(img)
        if not texts:
            # The QR sits 8 mm from the bottom-right corner; a phone shot taken
            # at an angle shrinks it. Try each corner at 2x.
            w, h = img.size
            cw, ch = w // 3, h // 3
            for box in ((0, 0, cw, ch), (w - cw, 0, w, ch), (0, h - ch, cw, h), (w - cw, h - ch, w, h)):
                crop = img.crop(box).resize((cw * 2, ch * 2))
                texts = _decode_all(crop)
                if texts:
                    break
    for text in texts:
        parsed = form_code.parse(text)
        if parsed and text.startswith(form_code.QR_PREFIX):
            return parsed
    return None


def read_code_with_model(provider, jpeg_bytes):
    """(form_id, page, None) read from the footer text by the model, or None.

    Returns (parsed | None, usage) so the caller can account the call."""
    blob, usage = provider.complete_structured(
        system=CODE_SYSTEM, user=CODE_USER, schema=CODE_SCHEMA, max_tokens=200,
        images=[('image/jpeg', jpeg_bytes)])
    text = (blob or {}).get('code') or ''
    parsed = form_code.parse(text) if text else None
    return parsed, usage
