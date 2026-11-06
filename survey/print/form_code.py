"""The form code printed on every page (spec printable-form).

A page says which printed form it belongs to, which numbered copy, and which
page it is:

* a QR in BOTH bottom corners — `MSFORM:<form>:<copy>:<page>:<pages>`, upper
  case so the QR takes alphanumeric mode (a smaller symbol at error level H),
  `<copy>` 0 on a form printed without copy numbers;
* a human line between them — `MS-<form> · #<copy> · Page 2 of 10`.

`<form>` is the `PrintedForm` id in a base32 alphabet without 0/O/1/I, so a
clerk can read it off a photocopy. The survey's uuid is deliberately NOT in
the code: a photographed sheet must not hand out the survey's public key.
Forms printed before copy numbers (change printable-form, #489) carry
`ms:form:<form>:<page>:<pages>`; `parse` still reads them.
"""
import re
from collections import namedtuple

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
_VALUE = {c: i for i, c in enumerate(ALPHABET)}
TEXT_PREFIX = 'MS-'
QR_PREFIX = 'MSFORM:'
_QR_RE = re.compile(r'^MSFORM:([2-9A-HJ-NP-Z]+):(\d+):(\d+):(\d+)$')
_QR_OLD_RE = re.compile(r'^ms:form:([2-9A-HJ-NP-Z]+):(\d+):(\d+)$')

# What a page's code says. `copy` is None on a form printed without numbers.
Code = namedtuple('Code', 'form_id copy page pages')


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


def page_text(form_id, page, pages, copy=None, page_label='Page %(n)s of %(total)s'):
    """The human line of the footer."""
    parts = [f'{TEXT_PREFIX}{encode(form_id)}']
    if copy:
        parts.append(f'#{copy}')
    parts.append(page_label % {'n': page, 'total': pages})
    return ' · '.join(parts)


def qr_payload(form_id, page, pages, copy=None):
    return f'{QR_PREFIX}{encode(form_id)}:{int(copy or 0)}:{page}:{pages}'


def parse(text):
    """A `Code` from a QR payload (current or pre-copy form), or None."""
    text = (text or '').strip()
    m = _QR_RE.match(text.upper())
    if m:
        copy = int(m.group(2))
        return Code(decode_id(m.group(1)), copy or None, int(m.group(3)), int(m.group(4)))
    m = _QR_OLD_RE.match(text)
    if m:
        return Code(decode_id(m.group(1)), None, int(m.group(2)), int(m.group(3)))
    return None


def qr_image(payload, px=256, error='m'):
    """A Pillow image of the QR for `payload` (segno draws it; no extra library)."""
    import io

    import segno
    from PIL import Image
    qr = segno.make(payload, error=error)
    buf = io.BytesIO()
    scale = max(1, px // (qr.symbol_size()[0]))
    qr.save(buf, kind='png', scale=scale, border=1)
    buf.seek(0)
    return Image.open(buf).convert('RGB')
