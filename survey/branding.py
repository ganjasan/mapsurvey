"""A workspace's brand on its public surfaces (change workspace-branding, #619).

One brand per workspace — `Organization.logo`, `accent_color`, `brand_name` — read today by the
public site (`/p/`) and its builder canvas, later by the respondent panel and the flyer (#220).
The accent is used for buttons with white text and for links on white, so a colour too light to
read is darkened here, never stored darker: the creator's colour stays what they chose.
"""
import re

DEFAULT_ACCENT = '#2f6fb0'
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
TEXT_CONTRAST = 4.5  # WCAG AA for body text


def _channel(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable(hex_color):
    """(colour to use, darkened?) — `hex_color` mixed toward black until white text on it, and it
    as text on white, reach TEXT_CONTRAST."""
    if not hex_color or not HEX.match(hex_color):
        return DEFAULT_ACCENT, False
    color = hex_color.lower()
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    for step in range(0, 101, 4):
        f = 1 - step / 100
        candidate = '#%02x%02x%02x' % (round(r * f), round(g * f), round(b * f))
        if contrast(candidate, '#ffffff') >= TEXT_CONTRAST:
            return candidate, step > 0
    return '#000000', True


def for_site(org):
    """What a site's templates need: {'name', 'logo_url', 'accent', 'darkened'}."""
    accent, darkened = readable(org.accent_color)
    return {
        'name': org.display_name,
        'logo_url': org.logo.url if org.logo else '',
        'accent': accent,
        'custom_accent': bool(org.accent_color),
        'darkened': darkened,
    }
