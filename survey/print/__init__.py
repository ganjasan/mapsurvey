"""Print pipeline (change printable-form, #489; epic #350 item 2).

What a survey looks like on paper: `pdf.build_form` renders the respondent
structure to a PDF through reportlab, `static_map` draws a section's map as an
image (Mapbox Static Images for the basemap, Pillow for the creator's reference
layers), `form_code` names the printed form on every page so a photo of a
filled sheet can be matched back (items 3 and 4 of the epic). The flyer
generator (#220) is the next consumer of the same page template and map.

Fonts: reportlab's built-in fonts are Latin-1 only, and a form prints survey
text in any of the 75 respondent languages, so DejaVu Sans ships here
(`fonts/`, Bitstream Vera licence). `register_fonts()` is idempotent and is
called by the document builder; nothing imports reportlab at Django start-up.
"""
import os
import threading

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FONT_REGULAR = 'DejaVuSans'
FONT_BOLD = 'DejaVuSans-Bold'

_registered = False
_lock = threading.Lock()


def register_fonts():
    """Register the bundled fonts with reportlab once per process."""
    global _registered
    if _registered:
        return
    with _lock:
        if _registered:
            return
        from reportlab.lib.fonts import addMapping
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, os.path.join(FONT_DIR, 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf')))
        # <b> inside a Paragraph resolves through the family mapping.
        addMapping(FONT_REGULAR, 0, 0, FONT_REGULAR)
        addMapping(FONT_REGULAR, 1, 0, FONT_BOLD)
        addMapping(FONT_REGULAR, 0, 1, FONT_REGULAR)
        addMapping(FONT_REGULAR, 1, 1, FONT_BOLD)
        _registered = True
