"""Move a creator template or stylesheet onto css/tokens.css (change tokens-editor-shell).

Every colour written in a CSS declaration (a <style> block, a stylesheet, a style="" attribute)
is replaced by the PURPOSE token for what it does where it stands — the same grey is muted text in
`color:` and a line in `border:` — and single black box shadows become --shadow-sm|md|lg by blur.
<script> blocks are left alone: a colour handed to Leaflet or written into an iframe's srcdoc
cannot read a CSS variable. Whatever the table does not know is listed, never guessed.

    python scripts/tokenise_colours.py FILE [FILE …]          # rewrite in place, print leftovers
    python scripts/tokenise_colours.py --dry-run FILE [FILE …]

Afterwards add the file to TOKENISED in survey/tests/test_design_tokens.py and lower the baseline
with scripts/colour_baseline.py.
"""
import re
import sys

T, L, B = 'text', 'line', 'bg'

# hex → token, or {role: token}. A role missing from a dict leaves the colour for a person.
COLOURS = {
    # greys: text
    '#111827': {T: 'color-text', B: 'surface-inverse'},
    '#1f2937': {T: 'color-text', B: 'surface-inverse'},
    '#1a1a1a': {T: 'color-text'}, '#1a1d21': {T: 'color-text'}, '#212529': {T: 'color-text'},
    '#343a40': {T: 'color-text'}, '#374151': {T: 'color-text'}, '#495057': {T: 'color-text'},
    '#4b5563': {T: 'color-text-muted'}, '#5f6368': {T: 'color-text-muted'},
    '#6b7280': {T: 'color-text-muted', L: 'color-text-muted', B: 'color-text-muted'},
    '#6c757d': {T: 'color-text-muted'}, '#6b6560': {T: 'color-text-muted'},
    '#868e96': {T: 'color-text-faint'}, '#9ca3af': {T: 'color-text-faint', L: 'color-border-strong'},
    '#9aa0a6': {T: 'color-text-faint', L: 'color-border-strong', B: 'color-text-faint'},
    '#adb5bd': {T: 'color-text-faint', L: 'color-border-strong'},
    '#c8c2b8': {T: 'color-text-faint'}, '#c4c7cf': {T: 'color-text-faint'},
    # greys: lines and surfaces
    '#d1d5db': {T: 'color-text-faint', L: 'color-border-strong', B: 'color-border-strong'},
    '#d5d8dc': {T: 'color-border-strong', L: 'color-border-strong'},
    '#ced4da': {L: 'color-border-strong'}, '#d1ccc5': {L: 'color-border-strong'},
    '#e5e7eb': {L: 'color-border', B: 'color-border'},
    '#dee2e6': {L: 'color-border'}, '#e9ecef': {L: 'color-border', B: 'surface-sunken'},
    '#eef0f3': {L: 'color-border'},
    '#f3f4f6': {L: 'color-border', B: 'surface-sunken'},
    '#f9fafb': {B: 'surface-muted'}, '#f8f9fa': {B: 'surface-muted'}, '#fafafa': {B: 'surface-muted'},
    '#f7f8fa': {B: 'surface-muted'}, '#f7f5f2': {B: 'page'},
    '#ffffff': {B: 'surface', T: 'color-on-action', L: 'surface'},
    # action: indigo, and the Bootstrap blues and teal it replaces
    '#4f46e5': 'color-action', '#6366f1': 'color-action', '#007bff': 'color-action',
    '#0d6efd': 'color-action', '#0b5ed7': 'color-action', '#2a7f6f': 'color-action',
    '#4338ca': 'color-action-hover', '#3730a3': 'color-action-hover', '#312e81': 'color-action-hover',
    '#1f6558': 'color-action-hover',
    '#eef2ff': {B: 'color-action-soft', L: 'color-action-line'}, '#e0e7ff': {B: 'color-action-soft', L: 'color-action-line'},
    '#f8f9ff': {B: 'color-action-soft'}, '#e7f1ff': {B: 'color-action-soft'}, '#f5faff': {B: 'color-action-soft'},
    '#c7d2fe': 'color-action-line', '#a5b4fc': 'color-action-line', '#b6d4fe': 'color-action-line',
    '#80bdff': 'color-action-line',
    # danger
    '#dc2626': 'color-danger', '#ef4444': 'color-danger', '#b91c1c': 'color-danger',
    '#dc3545': 'color-danger', '#d9534f': 'color-danger', '#b02a37': 'color-danger',
    '#991b1b': 'color-danger-hover', '#7f1d1d': 'color-danger-hover',
    '#fef2f2': {B: 'color-danger-soft'}, '#fee2e2': {B: 'color-danger-soft'}, '#fdf2f2': {B: 'color-danger-soft'},
    '#fecaca': {L: 'color-danger-line', B: 'color-danger-soft'}, '#fca5a5': {L: 'color-danger-line'},
    # success
    '#047857': 'color-success', '#198754': 'color-success', '#16a34a': 'color-success',
    '#22c55e': 'color-success', '#10b981': 'color-success', '#059669': 'color-success',
    '#15803d': 'color-success', '#065f46': 'color-success-hover', '#166534': 'color-success-hover',
    '#ecfdf5': {B: 'color-success-soft'}, '#f0fdf4': {B: 'color-success-soft'},
    '#dcfce7': {B: 'color-success-soft'}, '#d1fae5': {B: 'color-success-soft'},
    '#a7f3d0': {L: 'color-success-line'}, '#bbf7d0': {L: 'color-success-line'}, '#86efac': {L: 'color-success-line'},
    # warning
    '#f59e0b': 'color-warning', '#d97706': 'color-warning', '#b45309': 'color-warning',
    '#92400e': 'color-warning', '#9a3412': 'color-warning', '#c2410c': 'color-warning',
    '#ea580c': 'color-warning', '#8a6d3b': 'color-warning', '#d29a2c': 'color-warning',
    '#fef3c7': {B: 'color-warning-soft'}, '#fffbeb': {B: 'color-warning-soft'},
    '#fff7ed': {B: 'color-warning-soft'}, '#ffedd5': {B: 'color-warning-soft'},
    '#fcd34d': {L: 'color-warning-line'}, '#fde68a': {L: 'color-warning-line'},
    '#fed7aa': {L: 'color-warning-line'}, '#fdba74': {L: 'color-warning-line'},
    # rating stars
    '#f5b301': {T: 'color-rating'},
    # slate and other near-greys written by later modules
    '#0f172a': {T: 'color-text', B: 'surface-inverse'}, '#1e293b': {T: 'color-text', B: 'surface-inverse'},
    '#334155': {T: 'color-text'},
    '#475569': {T: 'color-text-muted'}, '#64748b': {T: 'color-text-muted'}, '#5f6b76': {T: 'color-text-muted'},
    '#5a6680': {T: 'color-text-muted'}, '#8a94a8': {T: 'color-text-muted'},
    '#94a3b8': {T: 'color-text-faint', L: 'color-border-strong'},
    '#a3acb6': {T: 'color-text-faint', L: 'color-border-strong'},
    '#cbd5e1': {T: 'color-text-faint', L: 'color-border-strong', B: 'color-border-strong'},
    '#c9d2dc': {T: 'color-text-faint', L: 'color-border-strong'}, '#c3c9d0': {T: 'color-text-faint', L: 'color-border-strong'},
    '#c3c8d1': {T: 'color-text-faint', L: 'color-border-strong'}, '#c4c7cc': {T: 'color-text-faint', L: 'color-border-strong'},
    '#d5dae0': {T: 'color-text-faint', L: 'color-border-strong', B: 'color-border-strong'},
    '#c8d6e8': {L: 'color-border-strong'},
    '#e2e8f0': {L: 'color-border', B: 'color-border'}, '#e4e7eb': {L: 'color-border', B: 'color-border'},
    '#e2e6ee': {L: 'color-border', B: 'color-border'}, '#e8eaed': {L: 'color-border', B: 'surface-sunken'},
    '#e2e3e5': {L: 'color-border', B: 'surface-sunken'}, '#e4e0d8': {L: 'color-border', B: 'surface-sunken'},
    '#f1f5f9': {L: 'color-border', B: 'surface-sunken'}, '#f1f2f4': {L: 'color-border', B: 'surface-sunken'},
    '#f0f0f4': {L: 'color-border', B: 'surface-sunken'},
    '#f8fafc': {B: 'surface-muted'}, '#f5f7fa': {B: 'surface-muted'}, '#fafbfc': {B: 'surface-muted'},
    '#f8f8fb': {B: 'surface-muted'},
    # Tailwind / Google blues → action
    '#2563eb': 'color-action', '#1a56db': 'color-action', '#2f6fb0': 'color-action', '#3b82f6': 'color-action',
    '#1d4ed8': 'color-action-hover', '#1e40af': 'color-action-hover',
    '#eff6ff': {B: 'color-action-soft', L: 'color-action-line'}, '#e8f0fe': {B: 'color-action-soft'},
    '#f7faff': {B: 'color-action-soft'}, '#dbeafe': {B: 'color-action-soft', L: 'color-action-line'},
    '#bfdbfe': 'color-action-line', '#d0d0ff': 'color-action-line', '#93c5fd': 'color-action-line',
    # Pro violet
    '#6d4ae0': 'color-pro', '#5b3fa8': 'color-pro-hover', '#5a3bc4': 'color-pro-hover',
    # more states
    '#28a745': 'color-success', '#e8f5ee': {B: 'color-success-soft'}, '#b7e0c8': {L: 'color-success-line'},
    '#b42318': 'color-danger', '#7c2d12': 'color-warning', '#fd7e14': 'color-warning', '#fb8c00': 'color-warning',
    '#fdf7ea': {B: 'color-warning-soft'},
}

# Translucent tones of a palette colour: (r, g, b) → token by role, the alpha chosen by the token.
TRANSLUCENT = {
    (79, 70, 229): {B: 'color-action-soft', L: 'color-action-line', T: 'color-action'},
    (37, 99, 235): {B: 'color-action-soft', L: 'color-action-line', T: 'color-action'},
    (99, 102, 241): {B: 'color-action-soft', L: 'color-action-line', T: 'color-action'},
    (109, 74, 224): {B: 'color-pro-soft', L: 'color-pro-line', T: 'color-pro'},
    (220, 38, 38): {B: 'color-danger-soft', L: 'color-danger-line', T: 'color-danger'},
}

COLOUR = re.compile(r'#[0-9a-fA-F]{6}\b|rgba?\([^)]*\)')
SCRIPT = re.compile(r'<script\b.*?</script>', re.S | re.I)
PROP = re.compile(r'([a-z-]+)\s*:\s*[^;{}"\']*$')
DARK = r'rgba\(\s*(?:0\s*,\s*0\s*,\s*0|15\s*,\s*23\s*,\s*42|17\s*,\s*24\s*,\s*39|31\s*,\s*41\s*,\s*55)\s*,\s*[\d.]+\s*\)'
ONE_SHADOW = (r'-?\d*\.?\d+(?:px)?\s+-?\d*\.?\d+(?:px)?\s+(\d*\.?\d+)(?:px)?(?:\s+-?\d*\.?\d+(?:px)?)?\s+' + DARK)
BLACK_SHADOW = re.compile(
    r'(box-shadow\s*:\s*)(' + ONE_SHADOW + r'(?:\s*,\s*' + ONE_SHADOW.replace('(\\d*', '(?:\\d*', 1) + r')*)'
    r'(?=\s*(?:!important)?\s*[;}"])')
FOCUS_SHADOW = re.compile(
    r'(box-shadow\s*:\s*)0 0 0 \d+px rgba\(\s*(?:42\s*,\s*127\s*,\s*111|79\s*,\s*70\s*,\s*229|37\s*,\s*99\s*,\s*235'
    r'|99\s*,\s*102\s*,\s*241|0\s*,\s*123\s*,\s*255|13\s*,\s*110\s*,\s*253)\s*,\s*[\d.]+\s*\)'
    r'(?=\s*(?:!important)?\s*[;}"])')
DANGER_FOCUS = re.compile(
    r'(box-shadow\s*:\s*)0 0 0 \d+px rgba\(\s*(?:220\s*,\s*38\s*,\s*38|239\s*,\s*68\s*,\s*68)\s*,\s*[\d.]+\s*\)'
    r'(?=\s*(?:!important)?\s*[;}"])')
RGBA = re.compile(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)')


def role(prop):
    if prop in ('color', 'fill', 'caret-color', 'text-decoration-color', 'accent-color', 'stroke'):
        return T
    if prop.startswith('background'):
        return B
    if prop.startswith(('border', 'outline', 'box-shadow', 'column-rule')):
        return L
    return None


def shadow_token(blur):
    blur = float(blur)
    return 'shadow-sm' if blur <= 4 else 'shadow-md' if blur <= 20 else 'shadow-lg'


def outside_scripts(text):
    spans, last = [], 0
    for m in SCRIPT.finditer(text):
        spans.append((last, m.start()))
        last = m.end()
    spans.append((last, len(text)))
    return spans


def tokenise(text):
    leftovers = []
    out, last = [], 0
    for start, end in outside_scripts(text):
        out.append(text[last:start])
        chunk = text[start:end]
        chunk = FOCUS_SHADOW.sub(lambda m: m.group(1) + 'var(--focus-ring)', chunk)
        chunk = DANGER_FOCUS.sub(lambda m: m.group(1) + 'var(--focus-ring-danger)', chunk)
        chunk = BLACK_SHADOW.sub(lambda m: m.group(1) + f'var(--{shadow_token(m.group(3))})', chunk)

        def swap(m):
            colour = m.group(0).lower()
            before = chunk[max(0, m.start() - 200):m.start()]
            prop_m = PROP.search(before)
            prop = prop_m.group(1) if prop_m else None
            if chunk[m.start() - 1:m.start()] in ('"', "'") or not prop:
                leftovers.append((colour, prop or '?'))
                return m.group(0)
            if prop.startswith('--'):
                leftovers.append((colour, prop))
                return m.group(0)
            entry = COLOURS.get(colour)
            if entry is None and (rgb := RGBA.match(colour)):
                entry = TRANSLUCENT.get(tuple(int(x) for x in rgb.groups()))
            token = entry.get(role(prop)) if isinstance(entry, dict) else entry
            if prop == 'accent-color' and entry is not None:
                token = 'color-action'
            if not token:
                leftovers.append((colour, prop))
                return m.group(0)
            return f'var(--{token})'

        out.append(COLOUR.sub(swap, chunk))
        last = end
    out.append(text[last:])
    return ''.join(out), leftovers


def main(argv):
    dry = '--dry-run' in argv
    for path in [a for a in argv if a != '--dry-run']:
        with open(path, encoding='utf-8') as f:
            text = f.read()
        new, leftovers = tokenise(text)
        if not dry and new != text:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new)
        print(f'{path}: {len(leftovers)} left')
        for colour, prop in leftovers:
            print(f'    {colour:28} {prop}')


if __name__ == '__main__':
    main(sys.argv[1:])
