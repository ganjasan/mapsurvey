"""The form code printed on every page (spec printable-form).

A page says which printed form it belongs to and which page it is:

* text in the footer — `MS-<form>-<page>`, e.g. `MS-7K-3`;
* a QR beside it — `ms:form:<form>:<page>:<pages>`.

`<form>` is the `PrintedForm` id in a base32 alphabet without 0/O/1/I, so a
clerk can read it off a photocopy. The survey's uuid is deliberately NOT in
the code: a photographed sheet must not hand out the survey's public key.
"""
import re

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
_VALUE = {c: i for i, c in enumerate(ALPHABET)}
TEXT_PREFIX = 'MS-'
QR_PREFIX = 'ms:form:'
_TEXT_RE = re.compile(r'^MS-([2-9A-HJ-NP-Z]+)-(\d+)$')
_QR_RE = re.compile(r'^ms:form:([2-9A-HJ-NP-Z]+):(\d+):(\d+)$')


def encode(form_id):
    """Base32 text for a positive integer id."""
    n = int(form_id)
    if n < 0:
        raise ValueError('form id must be positive')
    if n == 0:
        return ALPHABET[0]
    out = []
    while n:
        n, rem = divmod(n, 32)
        out.append(ALPHABET[rem])
    return ''.join(reversed(out))


def decode_id(text):
    """The integer behind an encoded form id (upper-cased, tolerant of the
    0/O 1/I confusions a human transcription makes)."""
    text = text.strip().upper().replace('O', '0').replace('I', '1').replace('0', '').replace('1', '')
    n = 0
    for ch in text:
        if ch not in _VALUE:
            raise ValueError(f'not a form code: {text!r}')
        n = n * 32 + _VALUE[ch]
    return n


def page_text(form_id, page):
    return f'{TEXT_PREFIX}{encode(form_id)}-{page}'


def qr_payload(form_id, page, pages):
    return f'{QR_PREFIX}{encode(form_id)}:{page}:{pages}'


def parse(text):
    """(form_id, page, pages|None) from either the text or the QR form, or None."""
    text = text.strip()
    m = _QR_RE.match(text)
    if m:
        return decode_id(m.group(1)), int(m.group(2)), int(m.group(3))
    m = _TEXT_RE.match(text.upper())
    if m:
        return decode_id(m.group(1)), int(m.group(2)), None
    return None


def qr_image(payload, px=256):
    """A Pillow image of the QR for `payload` (segno draws it; no extra library)."""
    import io

    import segno
    from PIL import Image
    qr = segno.make(payload, error='m')
    buf = io.BytesIO()
    scale = max(1, px // (qr.symbol_size()[0]))
    qr.save(buf, kind='png', scale=scale, border=1)
    buf.seek(0)
    return Image.open(buf).convert('RGB')
