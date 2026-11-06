"""Marks on the printed map → coordinates (epic #350 item 4; design D11).

Three steps, the first by the model and the rest local:
1. In the page's one vision call the model reports every mark drawn on the map
   frame — its label (A1, B2), its question, its vertices in image coordinates
   (0..1000 of the photo) and the answers written in the mark's row of the
   sub-question table (`prompts.py`, `extract.geo_items_for_page`).
2. The four black alignment squares are found on the photo (Pillow, no model)
   and a homography takes photo pixels to page millimetres. Without all four
   (a thumb, a crop) the map frame's box the model reported stands in — coarser,
   but a phone shot of the page rarely loses the frame.
3. Page millimetres inside the frame rectangle recorded at print time
   (`PrintedForm.layout[page]["map"]`: `x_mm`, `y_mm`, `w_mm`, `h_mm`, `bbox`,
   `zoom`) become a fraction of the frame, then a Web-Mercator world pixel
   inside the frame's bounds, then lng/lat — the frame is a Mercator image, so
   the fraction is linear in world pixels, not in degrees.

The result is a list of GeoJSON features in the dialect `_build_section_context`
already restores onto the map (`existing_geo_answers`): the operator sees the
marks where the respondent drew them, drags what is off, and saves through the
section POST like any other answer. Nothing here writes a row.
"""
import logging
import math
from collections import deque

from survey.print.static_map import project, unproject

logger = logging.getLogger('survey.paper')

# Page sizes in mm and the centre of an alignment square: MARK_INSET (8 mm) +
# half of MARK_SIZE (6 mm) from each edge (survey/print/pdf.py).
PAGE_MM = {'a4': (210.0, 297.0), 'letter': (215.9, 279.4)}
SQUARE_CENTRE_MM = 11.0
# The frame's rectangle plus this much on each side still counts as "on the map":
# a dot drawn on the border is a dot on the edge of the map.
FRAME_MARGIN = 0.03
# Dots a spray cloud is sampled into (per side of the grid over the shaded area).
SPRAY_GRID = 16
# Square detection works on a copy this wide at most: the squares are ~3 % of
# the page, a quarter of a megapixel is plenty and pure Python stays fast.
DETECT_SIDE = 900
PAGE_DETECT_SIDE = 2400
# The solid squares printed on the map frame's corners (survey/print/pdf.py,
# forms with map_rec['fiducials']); the frame's corners are their centres.
FIDUCIAL_MM = 5.0


# ── alignment squares ──────────────────────────────────────────────────────

def page_square_centres(paper):
    """[TL, TR, BL, BR] in mm from the page's top-left corner."""
    w, h = PAGE_MM.get(paper or 'a4', PAGE_MM['a4'])
    c = SQUARE_CENTRE_MM
    return [(c, c), (w - c, c), (c, h - c), (w - c, h - c)]


def _small_gray(img, side=DETECT_SIDE):
    gray = img.convert('L')
    scale = min(1.0, side / max(gray.size))
    if scale < 1.0:
        gray = gray.resize((max(1, round(gray.width * scale)), max(1, round(gray.height * scale))))
    return gray, scale


def _square_in(px, ox, oy, rw, rh, lo, hi, toward):
    """The solid, square, right-sized dark blob of a window nearest `toward`
    (a window pixel), or None. Thresholds from strict to loose: a square touching
    a shadow or the table edge merges into one huge blob at a soft threshold and
    stands alone at a hard one (page 7 of the first live check)."""
    values = [px[ox + x, oy + y] for y in range(rh) for x in range(rw)]
    ordered = sorted(values)
    p90 = ordered[int(len(ordered) * 0.9)]
    # Printed black photographs at 20–40; a dark table at 50–70; shadowed paper
    # at 100+. The first rung separates a square from the table it nearly touches.
    for thr in (max(30, min(45, p90 * 0.18)), max(35, min(60, p90 * 0.3)),
                max(35, min(90, p90 * 0.45)), max(40, min(110, p90 * 0.6))):
        best, best_d = None, None
        for minx, miny, maxx, maxy, count in _dark_components(values, rw, rh, thr):
            bw, bh = maxx - minx + 1, maxy - miny + 1
            if not (lo <= bw <= hi and lo <= bh <= hi):
                continue
            if not 0.6 <= bw / bh <= 1.6 or count / (bw * bh) < 0.7:
                continue
            if not _solid(values, rw, minx, miny, maxx, maxy, thr):
                continue   # a QR finder pattern: the right size and fill, a white ring inside
            cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
            d = (cx - toward[0]) ** 2 + (cy - toward[1]) ** 2
            if best is None or d < best_d:
                best, best_d = (ox + cx, oy + cy), d
        if best is not None:
            return best
    return None


def find_alignment_squares(img):
    """Centres of the four page-corner squares in photo pixels, [TL, TR, BL, BR],
    or None when any corner has no solid, square, right-sized dark blob."""
    # Full resolution (stored pages are ≤ 2200 px): on a 900-px copy of a photo
    # whose page fills a third of the frame the square is 6 px — the size of a
    # QR finder pattern's centre, which then passed for it (page 7, 2026-11-01).
    gray, scale = _small_gray(img, PAGE_DETECT_SIDE)
    w, h = gray.size
    px = gray.load()
    short = min(w, h)
    # 6 mm of a page that may fill a third of the photo's short side, up to a scan.
    lo, hi = short * 0.011, short * 0.07
    rw, rh = max(8, int(w * 0.3)), max(8, int(h * 0.3))
    windows = [(0, 0, (0, 0)), (w - rw, 0, (rw - 1, 0)), (0, h - rh, (0, rh - 1)), (w - rw, h - rh, (rw - 1, rh - 1))]
    found = []
    for ox, oy, toward in windows:
        best = _square_in(px, ox, oy, rw, rh, lo, hi, toward)
        if best is None:
            return None
        found.append((best[0] / scale, best[1] / scale))
    # Four solid squares are not necessarily the page's: a photo cropped to the
    # map shows the frame's fiducials in its corners. The page is portrait
    # (A4 0.71, letter 0.77); the frame is landscape (1.6). Perspective bends
    # the ratio, not that far.
    (tlx, tly), (trx, try_), (blx, bly), (brx, bry) = found
    width = (abs(trx - tlx) + abs(brx - blx)) / 2
    height = (abs(bly - tly) + abs(bry - try_)) / 2
    if height <= 0 or not 0.45 <= width / height <= 1.1:
        return None
    return found


def fiducial_targets(map_rec):
    """Where the fiducials are on the page, in mm: beside the frame's corners
    (`fiducials`), and halfway down its sides too (`fiducial_mids`, LAYOUT_VERSION 4)."""
    rx, ry, rw, rh = map_rec['x_mm'], map_rec['y_mm'], map_rec['w_mm'], map_rec['h_mm']
    dx = float(map_rec.get('fiducial_dx_mm') or 0)
    ys = [ry, ry + rh / 2, ry + rh] if map_rec.get('fiducial_mids') else [ry, ry + rh]
    return [(x, y) for y in ys for x in (rx - dx, rx + rw + dx)]


def find_frame_fiducials(img, frame_box, map_rec):
    """Centres of the squares printed beside the map frame (`fiducial_targets`
    order), in photo pixels, searched around where the model's frame box puts
    them; None per square not found, None altogether when none is."""
    if not frame_box or not map_rec or not map_rec.get('fiducials'):
        return None
    gray, scale = _small_gray(img)
    w, h = gray.size
    px = gray.load()
    y0, x0, y1, x1 = (v / 1000 for v in frame_box)
    # The fiducial is FIDUCIAL_MM wide and sits fiducial_dx_mm outside the frame's
    # left/right edges: size and aim from the box.
    frame_w = max(1.0, (x1 - x0) * w)
    per_mm = frame_w / float(map_rec['w_mm'])
    dx = float(map_rec.get('fiducial_dx_mm') or 0) * per_mm
    expect = FIDUCIAL_MM * per_mm
    lo, hi = expect * 0.45, expect * 2.2
    reach = max(12, int(expect * 2.5 + dx))
    rows = [y0 * h, (y0 + y1) / 2 * h, y1 * h] if map_rec.get('fiducial_mids') else [y0 * h, y1 * h]
    aims = [(x, y) for y in rows for x in (x0 * w - dx, x1 * w + dx)]
    found = []
    for ax, ay in aims:
        if not (-reach < ax < w + reach and -reach < ay < h + reach):
            found.append(None)   # beyond the photo's edge: a tight crop
            continue
        rw, rh = 2 * reach, 2 * reach
        ox, oy = max(0, min(w - rw, int(ax) - reach)), max(0, min(h - rh, int(ay) - reach))
        best = _square_in(px, ox, oy, rw, rh, lo, hi, (ax - ox, ay - oy))
        found.append((best[0] / scale, best[1] / scale) if best else None)
    return found if any(found) else None


# How much a landmark weighs in the fit: a fiducial sits beside the marks, a
# page square two hundred millimetres of bent paper away. With three or more
# fiducials the map is pinned by them alone and the squares only settle the
# degree of freedom they leave (copy 165: at 4:1 the compromise still put a
# dot 3 mm off; at 50:1 the fiducials are hit within half a millimetre).
# With one or two the squares must carry the fit.
FIDUCIAL_WEIGHT = 4.0
FIDUCIAL_WEIGHT_PINNED = 50.0
SQUARE_WEIGHT = 1.0


def _solid(values, rw, minx, miny, maxx, maxy, thr):
    """True when the blob is dark through and through: points on a ring at 0.2
    of its size around the centre are dark too. A QR finder pattern (the same
    size and fill as an alignment square on a phone photo) is white there."""
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    rx, ry = max(1.0, (maxx - minx) * 0.21), max(1.0, (maxy - miny) * 0.21)
    dark = 0
    for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
        x, y = int(round(cx + dx * rx)), int(round(cy + dy * ry))
        if values[y * rw + x] < thr:
            dark += 1
    return dark >= 7


def _dark_components(values, rw, rh, thr):
    """Connected dark blobs of one window (row-major `values`): (minx, miny, maxx, maxy, count)."""
    dark = [v < thr for v in values]
    seen = [False] * len(values)
    out = []
    for start in range(len(values)):
        if not dark[start] or seen[start]:
            continue
        seen[start] = True
        queue = deque([start])
        minx = maxx = start % rw
        miny = maxy = start // rw
        count = 0
        while queue:
            i = queue.popleft()
            count += 1
            x, y = i % rw, i // rw
            minx, maxx, miny, maxy = min(minx, x), max(maxx, x), min(miny, y), max(maxy, y)
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < rw and 0 <= ny < rh:
                    j = ny * rw + nx
                    if dark[j] and not seen[j]:
                        seen[j] = True
                        queue.append(j)
        if count >= 12:
            out.append((minx, miny, maxx, maxy, count))
    return out


# ── homography ─────────────────────────────────────────────────────────────

def homography(src, dst):
    """The 3×3 projective map taking the four `src` (x, y) to the four `dst`."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        rhs.append(u)
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        rhs.append(v)
    h = _solve(rows, rhs)
    if h is None:
        return None
    return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]]


def fit_homography(pairs, weights=None):
    """Least-squares projective map over ≥ 4 (src, dst) pairs, weighted: the
    normal equations of the DLT system. With exactly four pairs it is the exact
    homography. Paper is never flat on a table: a map registered to the page's
    four corners alone is 10 mm off in the middle, so every landmark found —
    the fiducials beside the frame (heavy), the page squares (light) — goes in."""
    if len(pairs) < 4:
        return None
    weights = weights or [1.0] * len(pairs)
    rows, rhs, ws = [], [], []
    for ((x, y), (u, v)), wgt in zip(pairs, weights):
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        rhs.append(u)
        ws.append(wgt)
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        rhs.append(v)
        ws.append(wgt)
    n = 8
    ata = [[0.0] * n for _ in range(n)]
    atb = [0.0] * n
    for row, b, wgt in zip(rows, rhs, ws):
        for i in range(n):
            if row[i] == 0.0:
                continue
            atb[i] += wgt * row[i] * b
            for j in range(n):
                ata[i][j] += wgt * row[i] * row[j]
    h = _solve(ata, atb)
    if h is None:
        return None
    return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]]


def _solve(a, b):
    """Gaussian elimination with partial pivoting; None on a singular system."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col] / m[col][col]
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def apply(h, x, y):
    """Photo pixel → page mm through a registration: a bare homography matrix,
    or a `{'h': matrix, 'tps': ...}` registration with its bend correction."""
    if isinstance(h, dict):
        base = apply(h['h'], x, y)
        if base is None:
            return None
        if h.get('tps'):
            cx, cy = _tps_value(h['tps'], x, y)
            return base[0] + cx, base[1] + cy
        return base
    d = h[2][0] * x + h[2][1] * y + h[2][2]
    if abs(d) < 1e-12:
        return None
    return ((h[0][0] * x + h[0][1] * y + h[0][2]) / d, (h[1][0] * x + h[1][1] * y + h[1][2]) / d)


# ── bend correction ────────────────────────────────────────────────────────
#
# Paper in a hand or on a lap is not a plane. The homography fits the landmarks
# as well as one plane can; what it leaves at each landmark (the residual, up to
# a centimetre at a far page corner) is interpolated by a thin-plate spline and
# added back, so a mark between two fiducials is corrected the way they were.
# Regularised per landmark by weight: a fiducial beside the frame is matched
# exactly, a page square on bent paper only loosely.

TPS_SMOOTHING = 0.1   # strong: the spline must follow the bend, not the noise of edge samples (1e-4 overfit them to 11 mm)


def fit_registration(pairs, weights, bend=None):
    """{'h': homography, 'tps': residual spline or None} over ≥ 4 (src, dst) pairs.
    `bend` flags the pairs whose residuals the spline follows — the landmarks ON
    the map's frame; a page corner's residual is paper bent OUTSIDE the frame,
    and following it dragged that bend into the map (copy 165: 5 mm → 9.5 mm)."""
    h = fit_homography(pairs, weights)
    if h is None:
        return None
    bend = bend or [True] * len(pairs)
    residuals = []
    for (src, dst), wgt, follow in zip(pairs, weights, bend):
        if not follow:
            continue
        mapped = apply(h, *src)
        if mapped is None:
            return {'h': h, 'tps': None}
        residuals.append((src, (dst[0] - mapped[0], dst[1] - mapped[1]), wgt))
    worst = max((abs(r[1][0]) + abs(r[1][1]) for r in residuals), default=0.0)
    if len(residuals) < 4 or worst < 0.3:
        return {'h': h, 'tps': None}   # flat enough: nothing to correct
    return {'h': h, 'tps': _tps_fit(residuals)}


def _invert3(h):
    """Inverse of a 3×3 (page mm → photo px), or None."""
    a, b, c = h[0]
    d, e, f = h[1]
    g, hh, i = h[2]
    det = a * (e * i - f * hh) - b * (d * i - f * g) + c * (d * hh - e * g)
    if abs(det) < 1e-12:
        return None
    return [[(e * i - f * hh) / det, (c * hh - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * hh - e * g) / det, (b * g - a * hh) / det, (a * e - b * d) / det]]


# Frame edges as landmarks: the printed frame is a rectangle of known size, and
# on a photo its border is where white paper meets the grey map (or the black
# border line). Sampled every few millimetres along all four sides it pins the
# bend of the page around the whole map — including the corner a tight crop
# lost its fiducial at.
EDGE_SAMPLES_PER_SIDE = 7
EDGE_WEIGHT = 10.0
EDGE_REACH_MM = 4.0
CORNER_WEIGHT = 30.0
INTERIOR_WEIGHT = 20.0


def find_frame_edges(gray, reg, map_rec, scale):
    """[(photo px, page mm)] on the frame's border, found from a first
    registration: for a point on the printed edge, predict where it is on the
    photo, look ±EDGE_REACH_MM along the edge's normal for the white→map step
    (or the border line), and keep what has contrast."""
    inv = _invert3(reg['h'] if isinstance(reg, dict) else reg)
    if inv is None:
        return []
    w, h = gray.size
    px = gray.load()
    rx, ry, rw, rh = map_rec['x_mm'], map_rec['y_mm'], map_rec['w_mm'], map_rec['h_mm']
    out = []
    for side in ('top', 'bottom', 'left', 'right'):
        for k in range(EDGE_SAMPLES_PER_SIDE):
            t = (k + 1) / (EDGE_SAMPLES_PER_SIDE + 1)
            if side in ('top', 'bottom'):
                mm = (rx + t * rw, ry if side == 'top' else ry + rh)
                outside = (mm[0], mm[1] - EDGE_REACH_MM if side == 'top' else mm[1] + EDGE_REACH_MM)
            else:
                mm = (rx if side == 'left' else rx + rw, ry + t * rh)
                outside = (mm[0] - EDGE_REACH_MM if side == 'left' else mm[0] + EDGE_REACH_MM, mm[1])
            inside = (2 * mm[0] - outside[0], 2 * mm[1] - outside[1])
            p_out = apply(inv, *outside)
            p_in = apply(inv, *inside)
            if p_out is None or p_in is None:
                continue
            p_out = (p_out[0] * scale, p_out[1] * scale)
            p_in = (p_in[0] * scale, p_in[1] * scale)
            n = 2 * int(max(abs(p_in[0] - p_out[0]), abs(p_in[1] - p_out[1]))) + 1
            if n < 9:
                continue
            profile, coords = [], []
            for i in range(n):
                s = i / (n - 1)
                x, y = p_out[0] + s * (p_in[0] - p_out[0]), p_out[1] + s * (p_in[1] - p_out[1])
                xi, yi = int(round(x)), int(round(y))
                if not (0 <= xi < w and 0 <= yi < h):
                    break
                profile.append(px[xi, yi])
                coords.append((x, y))
            if len(profile) < 9:
                continue
            edge = _edge_index(profile)
            if edge is None:
                continue
            out.append(((coords[edge][0] / scale, coords[edge][1] / scale), mm, side))
    return out


def frame_corners_from_edges(edges, map_rec):
    """The frame's corners as landmarks, from lines fitted through the edge
    samples of adjacent sides. An edge sample pins the paper only across its
    side; the corner of two fitted lines pins it both ways — which is what a
    corner that lost its fiducial to a tight crop needs (copy 165: 5.7 mm along
    the bottom edge with the border sampled but no corner)."""
    lines = {}
    for side in ('top', 'bottom', 'left', 'right'):
        pts = [src for src, _mm, s in edges if s == side]
        if len(pts) >= 3:
            lines[side] = _fit_line(pts)
    rx, ry, rw, rh = map_rec['x_mm'], map_rec['y_mm'], map_rec['w_mm'], map_rec['h_mm']
    out = []
    for (a, b), mm in ((('top', 'left'), (rx, ry)), (('top', 'right'), (rx + rw, ry)),
                       (('bottom', 'left'), (rx, ry + rh)), (('bottom', 'right'), (rx + rw, ry + rh))):
        if a in lines and b in lines:
            pt = _intersect(lines[a], lines[b])
            if pt is not None:
                out.append((pt, mm))
    return out


def _fit_line(pts):
    """Total least squares: (centre, unit direction) of the points' principal axis."""
    n = len(pts)
    cx, cy = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return (cx, cy), (math.cos(angle), math.sin(angle))


def _intersect(l1, l2):
    (x1, y1), (dx1, dy1) = l1
    (x2, y2), (dx2, dy2) = l2
    det = dx1 * dy2 - dy1 * dx2
    if abs(det) < 1e-9:
        return None
    t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / det
    return (x1 + t * dx1, y1 + t * dy1)


def _edge_index(profile):
    """Where the border is along an outside→inside profile: a dark line well
    below the paper, else the strongest sustained white→grey step; None when the
    profile has no contrast (a shadow, a hand, the table)."""
    k = max(2, len(profile) // 6)
    outside = sum(profile[:k]) / k
    darkest = min(range(len(profile)), key=lambda i: profile[i])
    if profile[darkest] < outside - 45:
        return darkest
    best, best_drop = None, 10.0
    for i in range(k, len(profile) - k):
        drop = sum(profile[i - k:i]) / k - sum(profile[i:i + k]) / k
        if drop > best_drop:
            best, best_drop = i, drop
    return best


def _tps_u(r2):
    return r2 * math.log(r2) if r2 > 0 else 0.0


def _tps_fit(residuals):
    """Thin-plate spline through (src px → residual mm), smoothed per point by
    1/weight. Coordinates are scaled to ~1 so the kernel is well conditioned."""
    pts = [r[0] for r in residuals]
    scale = max(1.0, max(max(abs(p[0]), abs(p[1])) for p in pts))
    xs = [(p[0] / scale, p[1] / scale) for p in pts]
    n = len(xs)
    rows = []
    for i in range(n):
        row = []
        for j in range(n):
            dx, dy = xs[i][0] - xs[j][0], xs[i][1] - xs[j][1]
            row.append(_tps_u(dx * dx + dy * dy))
        row[i] += TPS_SMOOTHING / max(residuals[i][2], 1e-6)
        row += [1.0, xs[i][0], xs[i][1]]
        rows.append(row)
    for k in range(3):
        rows.append([[1.0, xs[j][0], xs[j][1]][k] for j in range(n)] + [0.0, 0.0, 0.0])
    out = {'scale': scale, 'pts': xs}
    for axis in (0, 1):
        rhs = [r[1][axis] for r in residuals] + [0.0, 0.0, 0.0]
        sol = _solve([row[:] for row in rows], rhs)
        if sol is None:
            return None
        out['w' + 'xy'[axis]] = sol[:n]
        out['a' + 'xy'[axis]] = sol[n:]
    return out


def _tps_value(tps, x, y):
    sx, sy = x / tps['scale'], y / tps['scale']
    out = []
    for axis in 'xy':
        a = tps['a' + axis]
        v = a[0] + a[1] * sx + a[2] * sy
        for (px_, py_), wgt in zip(tps['pts'], tps['w' + axis]):
            dx, dy = sx - px_, sy - py_
            v += wgt * _tps_u(dx * dx + dy * dy)
        out.append(v)
    return out[0], out[1]


def photo_to_page(img, paper, frame_box=None, map_rec=None, frame_corners=None, reference=None):
    """(homography photo px → page mm, source) — `fiducials` from the squares
    beside the frame (closest to the marks, immune to paper curl, there even
    when the photo is cropped to the map), else `squares` from the page's
    alignment marks, else `frame` from the model's four corners of the frame
    (or, failing those, its box), or (None, None)."""
    # Every landmark found goes into one weighted fit: the fiducials beside the
    # frame (even three of them, when a tight crop lost one) pin the map down,
    # the page squares keep the fit sane where fiducials are missing.
    pairs, weights, bend, kinds = [], [], [], set()
    fiducials = find_frame_fiducials(img, frame_box, map_rec)
    if fiducials:
        found = [(src, dst) for src, dst in zip(fiducials, fiducial_targets(map_rec)) if src is not None]
        weight = FIDUCIAL_WEIGHT_PINNED if len(found) >= 3 else FIDUCIAL_WEIGHT
        for src, dst in found:
            pairs.append((src, dst))
            weights.append(weight)
            bend.append(True)
            kinds.add('fiducials')
    squares = find_alignment_squares(img)
    if squares:
        for src, dst in zip(squares, page_square_centres(paper)):
            pairs.append((src, dst))
            weights.append(SQUARE_WEIGHT)
            bend.append(False)   # a page corner bends outside the map: not the map's bend
        kinds.add('squares')
    if len(pairs) >= 4 and map_rec:
        first = fit_registration(pairs, weights, bend)
        if first is not None:
            # Second pass: the frame's own border, sampled all around, pins the
            # bend of the map where fiducials are missing or sparse.
            gray, scale = _small_gray(img, PAGE_DETECT_SIDE)
            edges = find_frame_edges(gray, first, map_rec, scale)
            if len(edges) < 8:
                edges = []
            else:
                kinds.add('edges')
            corners = frame_corners_from_edges(edges, map_rec)
            h = _fit_with_edges(pairs, weights, bend, edges, corners, map_rec, h=None)
            # Third pass: the printed map itself, matched inside the frame, for
            # the bow of the page that no border can see (survey/paper/texture.py).
            if h is not None and reference is not None:
                h = _refine_with_interior(h, gray if scale == 1.0 else img.convert('L'), reference,
                                          pairs, weights, bend, edges, corners, map_rec, kinds)
            if h is not None:
                return h, '+'.join(sorted(kinds))
    if map_rec:
        w, hgt = img.size
        src = _frame_quad(frame_corners)
        if src:
            src = [(x / 1000 * w, y / 1000 * hgt) for y, x in src]
        elif frame_box:
            y0, x0, y1, x1 = frame_box
            src = [(x0 / 1000 * w, y0 / 1000 * hgt), (x1 / 1000 * w, y0 / 1000 * hgt),
                   (x0 / 1000 * w, y1 / 1000 * hgt), (x1 / 1000 * w, y1 / 1000 * hgt)]
        if src:
            rx, ry, rw, rh = map_rec['x_mm'], map_rec['y_mm'], map_rec['w_mm'], map_rec['h_mm']
            dst = [(rx, ry), (rx + rw, ry), (rx, ry + rh), (rx + rw, ry + rh)]
            h = homography(src, dst)
            if h is not None:
                return h, 'frame'
    return None, None


INTERIOR_ROUNDS = 3        # match → refit, until the matches sit where the fit predicts
INTERIOR_SETTLED_PX = 2    # … within this many reference pixels (≈ 0.4 mm)


def _refine_with_interior(h, gray, reference, pairs, weights, bend, edges, corners, map_rec, kinds):
    """Rounds of texture matching inside the frame (survey/paper/texture.py), each
    on the photo rectified through the registration the previous round gave —
    a bend the first window clipped is within reach once the spline follows the
    matches around it. An edge sample pins the paper ACROSS its side; along it,
    it only repeats what the fit it was found with predicted, so every refit
    re-anchors the samples along their sides from the current fit."""
    from survey.paper import texture
    for _ in range(INTERIOR_ROUNDS):
        try:
            interior = texture.interior_landmarks(gray, h, map_rec, reference)
        except Exception:  # noqa: BLE001 — the interior pass is a refinement, never a failed read
            logger.warning('paper: interior matching failed', exc_info=True)
            return h
        if len(interior) < 3:
            return h
        kinds.add('interior')
        all_pairs = pairs + [(src, dst) for src, dst, _shift in interior]
        all_weights = weights + [INTERIOR_WEIGHT] * len(interior)
        all_bend = bend + [True] * len(interior)
        for _ in range(2):
            h = _fit_with_edges(all_pairs, all_weights, all_bend, edges, corners, map_rec, h=h) or h
        if max(shift for _src, _dst, shift in interior) <= INTERIOR_SETTLED_PX:
            break
    return h


def _fit_with_edges(pairs, weights, bend, edges, corners, map_rec, h=None):
    """One registration over the landmarks plus the edge samples and corners.
    With `h`, each edge sample's page point is re-anchored ALONG its side to
    where `h` sends the photo point (across the side it stays on the border)."""
    rx, ry, rw, rh = map_rec['x_mm'], map_rec['y_mm'], map_rec['w_mm'], map_rec['h_mm']
    all_pairs, all_weights, all_bend = list(pairs), list(weights), list(bend)
    for src, dst, side in edges:
        if h is not None:
            mapped = apply(h, *src)
            if mapped is not None:
                if side in ('top', 'bottom'):
                    dst = (min(rx + rw, max(rx, mapped[0])), dst[1])
                else:
                    dst = (dst[0], min(ry + rh, max(ry, mapped[1])))
        all_pairs.append((src, dst))
        all_weights.append(EDGE_WEIGHT)
        all_bend.append(True)
    for src, dst in corners:
        all_pairs.append((src, dst))
        all_weights.append(CORNER_WEIGHT)
        all_bend.append(True)
    return fit_registration(all_pairs, all_weights, all_bend)


def _frame_quad(corners):
    """The model's four frame corners as [TL, TR, BL, BR] in [y, x] 0..1000, or
    None: four in-range points sorted into that order by position."""
    pts = []
    for pt in corners or []:
        try:
            y, x = float(pt[0]), float(pt[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (0 <= y <= 1000 and 0 <= x <= 1000):
            return None
        pts.append((y, x))
    if len(pts) != 4:
        return None
    top = sorted(sorted(pts, key=lambda p: p[0])[:2], key=lambda p: p[1])
    bottom = sorted(sorted(pts, key=lambda p: p[0])[2:], key=lambda p: p[1])
    quad = [top[0], top[1], bottom[0], bottom[1]]
    if quad[1][1] - quad[0][1] < 50 or quad[3][1] - quad[2][1] < 50 or quad[2][0] - quad[0][0] < 50:
        return None
    return quad


# ── frame → world ──────────────────────────────────────────────────────────

def mm_to_lnglat(x_mm, y_mm, map_rec):
    """A page point inside (or just outside) the frame → (lng, lat), else None."""
    fx = (x_mm - map_rec['x_mm']) / map_rec['w_mm']
    fy = (y_mm - map_rec['y_mm']) / map_rec['h_mm']
    if not (-FRAME_MARGIN <= fx <= 1 + FRAME_MARGIN and -FRAME_MARGIN <= fy <= 1 + FRAME_MARGIN):
        return None
    fx, fy = min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy))
    west, south, east, north = map_rec['bbox']
    zoom = int(map_rec.get('zoom') or 12)
    x0, y0 = project(west, north, zoom)
    x1, y1 = project(east, south, zoom)
    lng, lat = unproject(x0 + fx * (x1 - x0), y0 + fy * (y1 - y0), zoom)
    return round(lng, 6), round(lat, 6)


def place_points(points_1000, h, img_size, map_rec):
    """Model vertices ([y, x] in 0..1000 of the photo) → [(lng, lat)], dropping what is off the map."""
    w, hgt = img_size
    out = []
    for pt in points_1000 or []:
        try:
            y, x = float(pt[0]), float(pt[1])
        except (TypeError, ValueError, IndexError):
            continue
        page = apply(h, x / 1000 * w, y / 1000 * hgt)
        if page is None:
            continue
        ll = mm_to_lnglat(page[0], page[1], map_rec)
        if ll is not None:
            out.append(ll)
    return out


def geometry_for(kind, coords):
    """A GeoJSON geometry for a mark of a geo question type, or None when the
    vertices cannot make one (a line of one point, an area of two)."""
    if kind == 'point':
        return {'type': 'Point', 'coordinates': [coords[0][0], coords[0][1]]} if coords else None
    if kind == 'line':
        return {'type': 'LineString', 'coordinates': [list(c) for c in coords]} if len(coords) >= 2 else None
    if kind in ('polygon', 'spraycan'):
        if len(coords) < 3:
            return None
        ring = [list(c) for c in coords]
        if ring[0] != ring[-1]:
            ring.append(list(ring[0]))
        if kind == 'polygon':
            return {'type': 'Polygon', 'coordinates': [ring]}
        return {'type': 'MultiPoint', 'coordinates': _spray_dots(ring)}
    return None


def _spray_dots(ring):
    """The shaded area as a cloud: a grid of dots inside the outline."""
    from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
    try:
        poly = Polygon(ring)
        if not poly.valid:
            poly = GEOSGeometry(poly.buffer(0).wkt)
    except Exception:  # noqa: BLE001 — a bad ring is no cloud
        return [list(c) for c in ring]
    minx, miny, maxx, maxy = poly.extent
    dots = []
    for i in range(SPRAY_GRID):
        for j in range(SPRAY_GRID):
            x = minx + (i + 0.5) / SPRAY_GRID * (maxx - minx)
            y = miny + (j + 0.5) / SPRAY_GRID * (maxy - miny)
            if poly.contains(Point(x, y)):
                dots.append([round(x, 6), round(y, 6)])
    return dots or [list(c) for c in ring]


# ── the page's marks → features per geo question ───────────────────────────

def place_marks(raw_marks, frame_box, geo_items, map_rec, img, paper, frame_corners=None, reference=None):
    """{geo code: field} for the page: `value` is the list of GeoJSON features
    (lng/lat, sub-answers as properties) in `existing_geo_answers`' shape,
    `marks` the model's vertices as reported, `placement` how the photo was
    registered. Without a registration the marks stay raw and the field is
    unreadable: the operator draws them by hand."""
    from survey import other_option
    from survey.paper.extract import _coerce_value

    by_code = {item['code']: item for item in geo_items}
    by_letter = {item['letter']: item for item in geo_items}
    grouped = {item['code']: [] for item in geo_items}
    for mark in raw_marks or []:
        if not isinstance(mark, dict):
            continue
        item = by_code.get(str(mark.get('question') or ''))
        if item is None:
            label = str(mark.get('label') or '').strip().upper()
            letter = label.rstrip('0123456789')
            item = by_letter.get(letter)
        if item is None:
            continue
        grouped[item['code']].append(mark)

    h, source = photo_to_page(img, paper, frame_box=frame_box, map_rec=map_rec, frame_corners=frame_corners,
                              reference=reference)
    # The ink (survey/paper/ink.py): what the respondent drew, read off the
    # registered photo. The model's marks then only NAME the ink marks.
    ink_marks = []
    if h is not None and reference is not None:
        try:
            from survey.paper import ink
            ink_marks = ink.find_marks(img, h, map_rec, reference)
            if any(item['type'] == 'point' for item in geo_items):
                ink_marks += ink.unprinted_dots(img, h, map_rec, reference)
        except Exception:  # noqa: BLE001 — the ink is a refinement, never a failed read
            logger.warning('paper: reading the ink failed', exc_info=True)
    ppm = reference.width / float(map_rec['w_mm']) if reference is not None else None
    kinds_on_page = {}
    for item in geo_items:
        kinds_on_page.setdefault(item['type'], []).append(item['code'])
    # Ink under a handwritten label (the model's `label_box`) is writing, whatever
    # shape it makes: "A2" is a stroke's length and a loop's roundness.
    label_boxes = [_box_1000(m.get('label_box')) for marks in grouped.values() for m in marks]
    label_boxes = [b for b in label_boxes if b]
    if label_boxes:
        ink_marks = [m for m in ink_marks if not _under_label(m, label_boxes, img.size)]
    out = {}
    for item in geo_items:
        marks = grouped[item['code']]
        candidates = [m for m in ink_marks if m['kind'] == item['type']]
        if not marks and not any(not m.get('weak') for m in candidates):
            continue
        field = {'marks': marks, 'placement': source, 'box': _box_of(frame_box), 'frame_corners': _frame_quad(frame_corners)}
        if h is None:
            field.update({'value': None, 'confidence': 0.0, 'unreadable': True})
            out[item['code']] = field
            continue
        # Every model mark meets the ink mark of its kind its vertices lie along;
        # what the ink shows and the model did not name becomes a numbered mark
        # of this question when no other question of the kind shares the page.
        pairs, used = _match_marks(marks, candidates, h, img.size, map_rec, ppm)
        # Ink the model did not name: every strong mark, and a fine pen's dot
        # (weak, print-tested) that is not a fragment of a glyph — the model
        # dropped A1 of three on copy 164 and the ink had it.
        unmatched_ink = [c for j, c in enumerate(candidates) if j not in used
                         and (not c.get('weak') or (c['kind'] == 'point' and not c.get('unprinted')
                                                    and not _touches_text(c, ink_marks, ppm)))]
        if len(kinds_on_page[item['type']]) > 1:
            unmatched_ink = []
        features, boxes, labels, confidence, lost, from_ink = [], [], [], 1.0, 0, 0
        used_numbers = set()
        for mark, _c in pairs:
            label = str(mark.get('label') or '').strip().upper()
            if label[len(item['letter']):].isdigit():
                used_numbers.add(int(label[len(item['letter']):]))
        for mark, candidate in pairs + [(None, c) for c in unmatched_ink]:
            if candidate is not None:
                coords = [mm_to_lnglat(map_rec['x_mm'] + u / ppm, map_rec['y_mm'] + v / ppm, map_rec) for u, v in candidate['px']]
                coords = [c for c in coords if c is not None]
                if candidate['kind'] == 'spraycan':
                    geometry = {'type': 'MultiPoint', 'coordinates': [list(c) for c in coords]} if coords else None
                else:
                    geometry = geometry_for(item['type'], coords)
                box = _photo_box(candidate['photo_bbox'], img.size)
            else:
                coords = place_points(mark.get('points'), h, img.size, map_rec)
                geometry = geometry_for(item['type'], coords)
                box = _mark_box(mark.get('points')) or _box_1000(mark.get('label_box'))
            if geometry is None:
                if candidate is None:
                    lost += 1   # the model's vertices make no shape: the operator draws it
                continue
            if mark is None:
                number = 1
                while number in used_numbers:
                    number += 1
                used_numbers.add(number)
                label, properties, mark_confidence = f"{item['letter']}{number}", {'question_id': item['code']}, INK_ONLY_CONFIDENCE
            else:
                label = str(mark.get('label') or '').strip().upper()
                properties = _mark_properties(item, mark, other_option, _coerce_value)
                try:
                    mark_confidence = float(mark.get('confidence', 1.0))
                except (TypeError, ValueError):
                    mark_confidence = 0.0
                if candidate is None and item['type'] != 'point' and ink_marks:
                    mark_confidence = min(mark_confidence, MODEL_ONLY_CONFIDENCE)   # the ink showed nothing here
            if candidate is not None:
                from_ink += 1
            boxes.append(box)
            labels.append(label)
            confidence = min(confidence, mark_confidence)
            features.append({'type': 'Feature', 'geometry': geometry, 'properties': properties})
        # `feature_boxes` / `feature_labels` run parallel to `value`: where each
        # mark is on the photo (the check scrolls the photo to a row's mark) and
        # what the respondent wrote next to it. Kept beside the features, never
        # in their properties — properties become sub-answers on save.
        field.update({'value': features or None, 'confidence': confidence if features else 0.0,
                      'unreadable': not features or lost > 0, 'feature_boxes': boxes, 'feature_labels': labels,
                      'from_ink': from_ink})
        out[item['code']] = field
    return out


INK_ONLY_CONFIDENCE = 0.5     # a mark the ink shows and the model did not name: shown, flagged
MODEL_ONLY_CONFIDENCE = 0.6   # a line or area the model reports and the ink does not show: flagged
MATCH_MM = 25.0               # how far the model's vertices may lie from the ink they mean
WEAK_MATCH_MM = 8.0           # … from a glyph-sized stroke or loop, which is probably writing
UNPRINTED_PENALTY_MM = 3.0    # a dot found without the print test (a POI icon could be one) yields to one found with it


def _match_marks(marks, candidates, h, img_size, map_rec, ppm):
    """[(model mark, ink candidate or None)]: each model mark paired with the
    ink mark of its kind its vertices lie closest to (the median distance of
    its vertices to the candidate's outline, within MATCH_MM — WEAK_MATCH_MM
    for a glyph-sized candidate), nearest pairs first, each candidate at most
    once. A line the pen lifted on is several ink pieces along one model mark:
    every further strong piece within reach of that mark is sewn onto its
    first, nearest ends together, so the gap the pen left closes."""
    if not candidates or ppm is None:
        return [(m, None) for m in marks], set()
    scored = []
    for i, mark in enumerate(marks):
        pts = _mark_ref_px(mark, h, img_size, map_rec, ppm)
        if not pts:
            continue
        for j, candidate in enumerate(candidates):
            dists = sorted(_distance_to_mark(p, candidate) for p in pts)
            median = dists[len(dists) // 2]
            reach = (WEAK_MATCH_MM if candidate.get('weak') else MATCH_MM) * ppm
            if candidate.get('unprinted'):
                median += UNPRINTED_PENALTY_MM * ppm   # a dot the print test admitted wins over one it did not
            if median <= reach:
                scored.append((median, i, j))
    scored.sort()
    taken_marks, taken_candidates, pairing = set(), set(), {}
    for _d, i, j in scored:
        if i in taken_marks or j in taken_candidates:
            continue
        taken_marks.add(i)
        taken_candidates.add(j)
        pairing[i] = dict(candidates[j])
    for _d, i, j in scored:
        if j in taken_candidates or i not in pairing or candidates[j].get('weak'):
            continue
        if pairing[i]['kind'] == 'line' and candidates[j]['kind'] == 'line':
            taken_candidates.add(j)
            pairing[i]['px'] = _sew(pairing[i]['px'], candidates[j]['px'])
            pairing[i]['photo_bbox'] = tuple(f(a, b) for f, a, b in zip((min, min, max, max), pairing[i]['photo_bbox'], candidates[j]['photo_bbox']))
    return [(mark, pairing.get(i)) for i, mark in enumerate(marks)], taken_candidates


def _mark_ref_px(mark, h, img_size, map_rec, ppm):
    """A model mark's vertices as reference pixels of the frame — or, for a mark
    the model could only LABEL (no points), the centre of its label box: the
    row is named there, and the drawn mark is the ink nearest to it."""
    pts = []
    for pt in mark.get('points') or []:
        try:
            y, x = float(pt[0]), float(pt[1])
        except (TypeError, ValueError, IndexError):
            continue
        page = apply(h, x / 1000 * img_size[0], y / 1000 * img_size[1])
        if page is not None:
            pts.append(((page[0] - map_rec['x_mm']) * ppm, (page[1] - map_rec['y_mm']) * ppm))
    if not pts:
        box = _box_1000(mark.get('label_box'))
        if box:
            page = apply(h, (box[1] + box[3]) / 2 / 1000 * img_size[0], (box[0] + box[2]) / 2 / 1000 * img_size[1])
            if page is not None:
                pts.append(((page[0] - map_rec['x_mm']) * ppm, (page[1] - map_rec['y_mm']) * ppm))
    return pts


def _sew(a, b):
    """Two polylines joined at their nearest ends, as one."""
    options = []
    for ea, pa in ((0, a[0]), (1, a[-1])):
        for eb, pb in ((0, b[0]), (1, b[-1])):
            options.append((((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5, ea, eb))
    _d, ea, eb = min(options)
    a = a[::-1] if ea == 0 else list(a)
    b = b[::-1] if eb == 1 else list(b)
    return a + b


def _distance_to_mark(p, candidate):
    """Distance from a reference pixel to an ink mark: to the dot, to the
    outline's segments, or to the nearest sampled pixel of a cloud."""
    px = candidate['px']
    if candidate['kind'] in ('point', 'spraycan') or len(px) < 2:
        return min(((p[0] - u) ** 2 + (p[1] - v) ** 2) ** 0.5 for u, v in px)
    segments = list(zip(px, px[1:]))
    if candidate['kind'] == 'polygon':
        segments.append((px[-1], px[0]))
    return min(_point_segment(p, a, b) for a, b in segments)


def _point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return ((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / float(dx * dx + dy * dy)))
    return ((p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2) ** 0.5


def table_rows(raw_marks, table_items):
    """{geo code: field} for rows of a marks table read on a page WITHOUT its map
    (`extract.table_items_for_page`): `rows` = [{label, properties, confidence}]
    with the row's answers coerced like a mark's, `rows_only` set; `merge_pages`
    attaches them to the map page's field as `rows_extra`."""
    from survey import other_option
    from survey.paper.extract import _coerce_value

    out = {}
    for item in table_items:
        rows, confidence = [], 1.0
        for mark in raw_marks:
            if str(mark.get('question') or '') != item['code']:
                continue
            properties = _mark_properties(item, mark, other_option, _coerce_value)
            if len(properties) <= 1:
                continue   # the row says nothing
            try:
                mark_confidence = float(mark.get('confidence', 1.0))
            except (TypeError, ValueError):
                mark_confidence = 0.0
            confidence = min(confidence, mark_confidence)
            rows.append({'label': str(mark.get('label') or '').strip().upper(), 'properties': properties,
                         'confidence': mark_confidence})
        if rows:
            out[item['code']] = {'rows': rows, 'rows_only': True,
                                 'marks': [m for m in raw_marks if str(m.get('question') or '') == item['code']],
                                 'confidence': confidence, 'unreadable': False}
    return out


def _mark_properties(item, mark, other_option, _coerce_value):
    """The feature properties of a model mark: the question and the row's answers."""
    properties = {'question_id': item['code']}
    for answer in mark.get('answers') or []:
        if not isinstance(answer, dict):
            continue
        code = str(answer.get('code') or '')
        sub = next((s for s in item.get('subs', []) if s['code'] == code), None)
        if sub is None:
            if code.endswith('__other'):
                base = code[:-len('__other')]
                if any(s['code'] == base for s in item.get('subs', [])) and answer.get('value') not in (None, ''):
                    properties[other_option.field_name(base)] = [str(answer['value']).strip()]
            continue
        value, ok = _coerce_value(sub, answer.get('value'))
        if value in (None, '', []):
            continue
        properties[code] = [str(v) for v in value] if isinstance(value, list) else [str(value)]
    return properties


def _touches_text(candidate, ink_marks, ppm):
    """True when the candidate's box lies within GLYPH_GAP_MM of a piece of writing: a
    fragment of a glyph, not a dot beside a label."""
    gap = GLYPH_GAP_MM * ppm
    u0, v0, u1, v1 = candidate['bbox']
    for other in ink_marks:
        if other['kind'] != 'text':
            continue
        a0, b0, a1, b1 = other['bbox']
        if u0 - gap <= a1 and a0 <= u1 + gap and v0 - gap <= b1 and b0 <= v1 + gap:
            return True
    return False


GLYPH_GAP_MM = 1.0


def _box_1000(value):
    """[ymin, xmin, ymax, xmax] in 0..1000 from the model, or None."""
    try:
        y0, x0, y1, x1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not (0 <= y0 < y1 <= 1000 and 0 <= x0 < x1 <= 1000):
        return None
    return [y0, x0, y1, x1]


def _under_label(mark, label_boxes, img_size):
    """True when most of an ink mark's photo rectangle lies inside a label box."""
    x0, y0, x1, y1 = mark['photo_bbox']
    w, h = img_size
    mx0, my0, mx1, my1 = x0 / w * 1000, y0 / h * 1000, x1 / w * 1000, y1 / h * 1000
    area = max(1.0, (mx1 - mx0) * (my1 - my0))
    for ly0, lx0, ly1, lx1 in label_boxes:
        pad = 8   # the model's box is tight; ink bleeds past it
        ix = max(0.0, min(mx1, lx1 + pad) - max(mx0, lx0 - pad))
        iy = max(0.0, min(my1, ly1 + pad) - max(my0, ly0 - pad))
        if ix * iy >= 0.6 * area:
            return True
    return False


def _photo_box(photo_bbox, img_size):
    """An ink mark's photo rectangle → [ymin, xmin, ymax, xmax] in 0..1000, padded."""
    x0, y0, x1, y1 = photo_bbox
    w, h = img_size
    pad = 25
    return [max(0, int(y0 / h * 1000 - pad)), max(0, int(x0 / w * 1000 - pad)),
            min(1000, int(y1 / h * 1000 + pad)), min(1000, int(x1 / w * 1000 + pad * 2))]


def _mark_box(points):
    """[ymin, xmin, ymax, xmax] around a mark's vertices, padded, in 0..1000."""
    ys, xs = [], []
    for pt in points or []:
        try:
            ys.append(float(pt[0]))
            xs.append(float(pt[1]))
        except (TypeError, ValueError, IndexError):
            continue
    if not ys:
        return None
    pad = 25
    return [max(0, int(min(ys) - pad)), max(0, int(min(xs) - pad)),
            min(1000, int(max(ys) + pad)), min(1000, int(max(xs) + pad * 2))]


def _box_of(frame_box):
    from survey.paper.extract import _box
    return _box(frame_box)
