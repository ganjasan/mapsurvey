"""Marks on the printed map found in the INK, not asked of the model (change
paper-photo-entry, the hybrid; owner 2026-11-01: "AI is not needed for the map").

Once the photo is registered to the printed frame (`survey/paper/marks.py`,
`survey/paper/texture.py`), what the respondent drew is what the photo has
that the printed map does not. Two readings of that: darker than the paper around it (a shadow is not darker than its own
surroundings) and darker than the printed map expects there (a street name
is dark in the photo and the reference alike). The mask is split into
connected components and each is read as what it is: a cluster of short
strokes (hatching: a spray area), a closed loop (an area), a stroke with two
ends (a line), a filled disc (a point), or none of those (handwriting: a
label, which the model reads). The model's marks then only NAME what the ink
drew — the row's label and answers are matched to the nearest ink mark of the
question's kind; its vertices are a fallback for a mark the ink did not show.

Everything here works in REFERENCE pixels (`texture.REF_WIDTH` across the
frame, ≈ 5 px/mm) and returns geometry in those pixels; `marks.place_marks`
turns them into millimetres and coordinates.
"""
import logging

import numpy as np

from survey.paper import texture

log = logging.getLogger('survey.paper')

LOCAL_MM = 8.0            # the window the paper's own brightness and colour are taken over
COLOUR_THRESHOLD = 0.015  # a channel's share of the pixel, against the paper's: a blue ballpoint 0.02–0.1, print and shadow under 0.01
COLOUR_DARK_THRESHOLD = 3 # … and at least a little darker than the paper
COLOUR_DIFF_THRESHOLD = 15 # … and darker than the darkest print within PRINT_REACH_PX: a printed line under smeared colour is not
COLOUR_PRINT_LIGHT = 150  # … on print lighter than this (averaged over ±PRINT_REACH_PX): JPEG colour fringes live on dark print
DARK_THRESHOLD = 50       # of 255: darker than the paper's mean over LOCAL_MM around the pixel — a pen is 80–150, the edge of a shadow under 48
DIFF_THRESHOLD = 40       # of 255, both stretched to full range: darker than the darkest print within PRINT_REACH_PX
PRINT_REACH_PX = 3        # registration slack on thin print
PRINT_MIN = 60            # no reading where the print averaged over ±PRINT_REACH_PX is near black (the scale bar, a route shield)
NEAR_MM = 3.0             # the small window of the darkness reading
NEAR_THRESHOLD = 30       # darker than the 3-mm surroundings by this much: a stroke is, a shadow's gradient is not
MIN_COMPONENT_PX = 12
BRIDGE_PX = 2             # closing radius: a ballpoint skips, a photocopy breaks a stroke
BORDER_MM = 1.5           # the frame's own border line and its registration fringe
EDGE_ZONE_MM = 8.0        # a line along a frame side within this is the border off its registration (a curled page)
TEXT_MAX_MM = 12.0        # a label ("A2") is up to this tall; a stroke or loop boxed under it is weak: kept only when the model saw a mark there
DOT_DIAMETER_MM = (1.7, 3.2)   # a glyph filled by a thick pen is a 4-mm blob, a fragment of a glyph under 1.7 mm; a dot is neither
DOT_WEAK_MIN_MM = 1.0          # … but a fine pen's dot is 1.2 mm: weak, kept when the model's mark lies within WEAK reach
DOT_MIN_DISCNESS = 0.5
LINE_MIN_MM = 6.0         # a stroke shorter than this is a glyph
LOOP_MIN_HOLE_MM2 = 3.0   # the inside of a drawn area; a letter's counter is smaller
HATCH_DILATE_MM = 1.5     # strokes closer than this belong to one hatched area
HATCH_MIN_STROKES = 5
HATCH_MAX_STROKE_MM = 7.0
HATCH_MIN_STROKE_MM = 3.0   # a hatching stroke; a fragment of a glyph is shorter
SIMPLIFY_MM = 0.8
SPRAY_STEP_PX = 3
JOIN_MM = 8.0             # line pieces whose ends are this close are one stroke
CLOSE_MIN_MM = 20.0       # a sewn line at least this long whose ends meet is an outline (an area)
CLOSE_GAP_SHARE = 0.2     # … "meet" = within JOIN_MM or a fifth of its length (an area's last side is often left open)
SCRIBBLE_THICKNESS_MM = 3.0   # area / skeleton length above this is a filled scribble, not a bridged pen line (≤ 2 mm)
LINE_MIN_COVER = 0.7      # longest path / skeleton pixels: a stroke is one path, a glyph pair branches
LINE_PIECE_MIN_MM = 3.0   # a glyph-sized stroke counts only when it sews onto a real line
GLYPH_THICKNESS_MM = 2.0  # area / skeleton length of a glyph-sized blob above this is writing, not a stroke
SMALL_LOOP_MIN_MM = 4.0   # a drawn circle under the glyph size still counts when it is mostly hole


def find_marks(img, reg, map_rec, ref):
    """[{'kind', 'px': [(u, v), …], 'bbox': (u0, v0, u1, v1)}] — the ink marks of a
    registered map page in reference pixels, plus the labels' boxes under
    kind 'text'. `img` is the page (RGB), `reg` the registration, `ref` the
    reference image."""
    mask, ppm, maps = ink_mask(img, reg, map_rec, ref)
    if mask is None:
        return []
    found = classify(mask, ppm)
    px_x, px_y = maps
    h, w = mask.shape
    for mark in found:
        # Where the mark is on the PHOTO (the check scrolls the picture to it).
        u0, v0, u1, v1 = mark['bbox']
        corners = [(min(w - 1, max(0, int(u))), min(h - 1, max(0, int(v)))) for u, v in ((u0, v0), (u1, v0), (u0, v1), (u1, v1))]
        xs = [float(px_x[v, u]) for u, v in corners]
        ys = [float(px_y[v, u]) for u, v in corners]
        mark['photo_bbox'] = (min(xs), min(ys), max(xs), max(ys))
    return found


def unprinted_dots(img, reg, map_rec, ref):
    """Dots found WITHOUT the print test — darker than the paper around them,
    whatever is printed beneath — as weak 'point' marks. A dot drawn on a
    street name is no darker than the name's print within 3 px and the mask
    loses it; the model's mark beside it is what admits one of these."""
    ref_a = np.asarray(ref, dtype=np.float32)
    rh, rw = ref_a.shape
    ppm = rw / float(map_rec['w_mm'])
    maps = texture._inverse_maps(reg, map_rec['x_mm'], map_rec['y_mm'], ppm, 0, rw, 0, rh)
    if maps is None:
        return []
    gray = texture._bilinear(np.asarray(img.convert('L'), dtype=np.float32), *maps)
    window = 2 * int(round(LOCAL_MM * ppm / 2)) + 1
    dark = _local_mean(gray, window) - gray
    near = _local_mean(gray, 2 * int(round(NEAR_MM * ppm / 2)) + 1) - gray
    mask = (dark > DARK_THRESHOLD) & (near > NEAR_THRESHOLD)
    border = int(round(BORDER_MM * ppm))
    mask[:border, :] = mask[-border:, :] = False
    mask[:, :border] = mask[:, -border:] = False
    out = []
    px_x, px_y = maps
    for blob in _components(mask):
        if len(blob) < MIN_COMPONENT_PX:
            continue
        dot = _as_dot(blob, ppm)
        if dot is None:
            continue
        dot['weak'] = True
        dot['unprinted'] = True
        u0, v0, u1, v1 = dot['bbox']
        corners = [(min(rw - 1, max(0, int(u))), min(rh - 1, max(0, int(v)))) for u, v in ((u0, v0), (u1, v0), (u0, v1), (u1, v1))]
        dot['photo_bbox'] = (min(float(px_x[v, u]) for u, v in corners), min(float(px_y[v, u]) for u, v in corners),
                             max(float(px_x[v, u]) for u, v in corners), max(float(px_y[v, u]) for u, v in corners))
        out.append(dot)
    return out


def ink_mask(img, reg, map_rec, ref):
    """(boolean array the size of `ref`, px per mm, the photo-pixel maps) of the
    ink on the frame — strokes as the pen left them, not yet bridged — or
    (None, None, None)."""
    ref_a = np.asarray(ref, dtype=np.float32)
    rh, rw = ref_a.shape
    ppm = rw / float(map_rec['w_mm'])
    maps = texture._inverse_maps(reg, map_rec['x_mm'], map_rec['y_mm'], ppm, 0, rw, 0, rh)
    if maps is None:
        return None, None, None
    # Two pens, two readings, one mask. A coloured pen (a blue ballpoint) is
    # what differs IN COLOUR from the paper around it: each channel's share of
    # the pixel's brightness, less its mean over LOCAL_MM — a warm lamp tints
    # the whole page alike and drops out, a shadow has the paper's colour and
    # drops out — plus a little darker than that paper, so JPEG chroma noise on
    # near-black print does not count. A black pen is what is darker than the
    # paper around it (a shadow is not darker than its own surroundings) AND
    # darker than anything printed within two pixels (the reference's local
    # minimum: a street name a pixel off would otherwise read as ink). No
    # morphological opening: a 0.5-mm stroke is 2–3 px here and an opening
    # erases it; isolated noise goes with the component-size floor instead.
    channels = [texture._bilinear(np.asarray(img.getchannel(c), dtype=np.float32), *maps) for c in ('R', 'G', 'B')]
    gray = (channels[0] + channels[1] + channels[2]) / 3.0
    window = 2 * int(round(LOCAL_MM * ppm / 2)) + 1
    dark = _local_mean(gray, window) - gray
    total = np.maximum(channels[0] + channels[1] + channels[2], 1.0)
    shares = [c / total - _local_mean(c / total, window) for c in channels]
    colour = np.maximum(np.maximum(shares[0], shares[1]), shares[2]) - np.minimum(np.minimum(shares[0], shares[1]), shares[2])
    # The darkness reading is against the DARKEST print within PRINT_REACH_PX
    # (a street name a few pixels off its print — a glare band, a fold — is
    # then no darker than expected and not ink; against the print's average it
    # was, and so was every line of a high-contrast map). Solid black print
    # (the scale bar, a route shield) is no ground for either reading.
    stretched = texture._stretch(ref_a)
    diff = _local_min(stretched, PRINT_REACH_PX) - texture._stretch(gray)
    printed = _local_mean(stretched, 2 * PRINT_REACH_PX + 1)
    # A pen stroke is also darker than its NEAR surroundings (NEAR_MM): the dark
    # side of a shadow's edge is darker than the 8-mm mean, not than its 3-mm one.
    near = _local_mean(gray, 2 * int(round(NEAR_MM * ppm / 2)) + 1) - gray
    # The colour reading only on light print and only where the pixel is darker
    # than the print expects: JPEG chroma subsampling smears a stroke's colour
    # over a 2-mm block around it, and a printed line inside that block took the
    # ink's colour and passed for a stroke of its own.
    mask = (((colour > COLOUR_THRESHOLD) & (dark > COLOUR_DARK_THRESHOLD) & (diff > COLOUR_DIFF_THRESHOLD) & (printed > COLOUR_PRINT_LIGHT))
            | ((dark > DARK_THRESHOLD) & (near > NEAR_THRESHOLD) & (diff > DIFF_THRESHOLD))) & (printed > PRINT_MIN)
    border = int(round(BORDER_MM * ppm))
    mask[:border, :] = mask[-border:, :] = False
    mask[:, :border] = mask[:, -border:] = False
    return mask, ppm, maps


def classify(mask, ppm):
    """The components of an ink mask as marks (see `find_marks`). Hatching and
    dots are read on the strokes as they are; what remains is bridged
    (`BRIDGE_PX`: a ballpoint skips) before loops, lines and labels are read,
    and line pieces whose ends meet are sewn into one."""
    comps = [c for c in _components(mask) if len(c) >= MIN_COMPONENT_PX]
    out = []
    # Hatching is read twice: on the strokes as the pen left them (a hatch of
    # 1-mm spacing bridges into one blob) and again on the bridged strokes (a
    # hatch a ballpoint skipped on is whole only then).
    comps = _take_hatched(comps, mask.shape, ppm, out)
    rest = []
    for blob in comps:
        dot = _as_dot(blob, ppm)
        if dot is not None:
            out.append(dot)
        else:
            rest.append(blob)
    bridged = np.zeros_like(mask)
    for blob in rest:
        for y, x in blob:
            bridged[y, x] = True
    bridged = _close(bridged, BRIDGE_PX)
    comps = [c for c in _components(bridged) if len(c) >= MIN_COMPONENT_PX]
    comps = _take_hatched(comps, mask.shape, ppm, out)
    lines = []
    for blob in comps:
        mark = _read_component(blob, ppm)
        if mark['kind'] == 'line':
            lines.append(mark)
        else:
            out.append(mark)
    out.extend(_sew_lines(lines, ppm))
    h, w = mask.shape
    return [m for m in out if not _along_frame_edge(m, w, h, ppm)]


def _along_frame_edge(mark, w, h, ppm):
    """A line lying within EDGE_ZONE_MM of a frame side and running along it is
    the frame's own border, where a curled page pulled it off its registration."""
    if mark['kind'] != 'line':
        return False
    u0, v0, u1, v1 = mark['bbox']
    zone = EDGE_ZONE_MM * ppm
    across, along = (u1 - u0 + 1, v1 - v0 + 1)
    if (u0 <= zone or u1 >= w - zone) and along >= 4 * across:
        return True
    across, along = (v1 - v0 + 1, u1 - u0 + 1)
    return (v0 <= zone or v1 >= h - zone) and along >= 4 * across


# ── reading one component ──────────────────────────────────────────────────

def _mark(kind, px, blob):
    ys = [p[0] for p in blob]
    xs = [p[1] for p in blob]
    return {'kind': kind, 'px': px, 'bbox': (min(xs), min(ys), max(xs), max(ys)), 'area': len(blob)}


def _as_dot(blob, ppm):
    """A filled disc 0.8–4.5 mm across → a 'point' mark, else None."""
    ys = [p[0] for p in blob]
    xs = [p[1] for p in blob]
    bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    area = len(blob)
    diameter = 2 * (area / np.pi) ** 0.5
    discness = area / (np.pi * (max(bw, bh) / 2.0) ** 2)
    if DOT_WEAK_MIN_MM * ppm <= diameter <= DOT_DIAMETER_MM[1] * ppm and discness >= DOT_MIN_DISCNESS:
        mark = _mark('point', [(sum(xs) / float(area), sum(ys) / float(area))], blob)
        if diameter < DOT_DIAMETER_MM[0] * ppm:
            mark['weak'] = True   # a fine pen's dot, or a fragment of a glyph: the model's mark nearby decides
        return mark
    return None


def _read_component(blob, ppm):
    """A bridged component as a 'polygon' (closed loop), 'spraycan' (a dense
    scribble: far thicker than a pen stroke), 'line' (a long stroke with two
    ends) or 'text' (anything glyph-sized that is none of those)."""
    ys = [p[0] for p in blob]
    xs = [p[1] for p in blob]
    y0, x0, y1, x1 = min(ys), min(xs), max(ys), max(xs)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    area = len(blob)
    crop = np.zeros((bh + 2, bw + 2), dtype=bool)
    for y, x in blob:
        crop[y - y0 + 1, x - x0 + 1] = True
    small = max(bw, bh) <= TEXT_MAX_MM * ppm
    filled, hole_area = _fill_holes(crop)
    if hole_area >= LOOP_MIN_HOLE_MM2 * ppm * ppm and not small:
        ring = _trace_boundary(filled)
        if len(ring) >= 4:
            ring = _simplify([(x + x0 - 1, y + y0 - 1) for y, x in ring], SIMPLIFY_MM * ppm)
            if len(ring) >= 3:
                return _mark('polygon', ring, blob)
    if hole_area >= LOOP_MIN_HOLE_MM2 * ppm * ppm and small and max(bw, bh) >= SMALL_LOOP_MIN_MM * ppm:
        # A coin-sized drawn circle, or a glyph with a counter (D, O, 8)? Round
        # outside and hollow — kept only when the model also saw an area here.
        roundness = float(filled.sum()) / (np.pi * (max(bw, bh) / 2.0) ** 2)
        if roundness >= 0.55:
            ring = _trace_boundary(filled)
            ring = _simplify([(x + x0 - 1, y + y0 - 1) for y, x in ring], SIMPLIFY_MM * ppm)
            if len(ring) >= 3:
                mark = _mark('polygon', ring, blob)
                mark['weak'] = True
                return mark
    skeleton = _thin(crop)
    path = _longest_path(skeleton)
    length = sum(((path[i][0] - path[i - 1][0]) ** 2 + (path[i][1] - path[i - 1][1]) ** 2) ** 0.5 for i in range(1, len(path)))
    cover = length / max(1.0, float(skeleton.sum()))
    if not small and length > 0 and area / length > SCRIBBLE_THICKNESS_MM * ppm:
        px = [(x, y) for y, x in blob if y % SPRAY_STEP_PX == 0 and x % SPRAY_STEP_PX == 0]
        return _mark('spraycan', px, blob)
    if small and length > 0 and area / length > GLYPH_THICKNESS_MM * ppm:
        # Glyph-sized and far thicker than the pen's line: letters pile ink on
        # top of ink ("A2" came out 2.3 mm thick, every stroke on the page under 1.7).
        return _mark('text', [((x0 + x1) / 2.0, (y0 + y1) / 2.0)], blob)
    if length >= LINE_MIN_MM * ppm and not small and cover >= LINE_MIN_COVER:
        line = _simplify([(x + x0 - 1, y + y0 - 1) for y, x in path], SIMPLIFY_MM * ppm)
        if len(line) >= 2:
            return _mark('line', line, blob)
    if small and cover >= LINE_MIN_COVER and length >= LINE_PIECE_MIN_MM * ppm:
        line = _simplify([(x + x0 - 1, y + y0 - 1) for y, x in path], SIMPLIFY_MM * ppm)
        if len(line) >= 2:
            mark = _mark('line', line, blob)
            mark['weak'] = True
            return mark
    return _mark('text', [((x0 + x1) / 2.0, (y0 + y1) / 2.0)], blob)


def _sew_lines(lines, ppm):
    """Line pieces whose ends lie within JOIN_MM of each other become one line
    (a ballpoint skips, a photocopy drops a stroke); pieces shorter than
    LINE_MIN_MM that join nothing are glyphs."""
    reach = JOIN_MM * ppm
    pieces = [list(m['px']) for m in lines]
    strong = [not m.get('weak') for m in lines]
    sewn = [1] * len(lines)
    changed = True
    while changed and len(pieces) > 1:
        changed = False
        best = None
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                for ei, pi in ((0, pieces[i][0]), (1, pieces[i][-1])):
                    for ej, pj in ((0, pieces[j][0]), (1, pieces[j][-1])):
                        dist = ((pi[0] - pj[0]) ** 2 + (pi[1] - pj[1]) ** 2) ** 0.5
                        if dist <= reach and (best is None or dist < best[0]):
                            best = (dist, i, j, ei, ej)
        if best is not None:
            _dist, i, j, ei, ej = best
            a, b = pieces[i], pieces[j]
            if ei == 0:
                a = a[::-1]       # a's end meets b
            if ej == 1:
                b = b[::-1]       # b's start meets a's end
            pieces[i] = a + b
            strong[i] = strong[i] or strong[j]
            sewn[i] += sewn[j]
            del pieces[j]
            del strong[j]
            del sewn[j]
            changed = True
    out = []
    for px, is_strong, count in zip(pieces, strong, sewn):
        px = _simplify(px, SIMPLIFY_MM * ppm)
        length = sum(((px[i][0] - px[i - 1][0]) ** 2 + (px[i][1] - px[i - 1][1]) ** 2) ** 0.5 for i in range(1, len(px)))
        if length < LINE_PIECE_MIN_MM * ppm:
            continue
        xs = [p[0] for p in px]
        ys = [p[1] for p in px]
        gap = ((px[0][0] - px[-1][0]) ** 2 + (px[0][1] - px[-1][1]) ** 2) ** 0.5
        mark = {'kind': 'line', 'px': px, 'bbox': (min(xs), min(ys), max(xs), max(ys)), 'area': int(length)}
        is_strong = is_strong or (count > 1 and length >= TEXT_MAX_MM * ppm)   # sewn pieces longer than any label (one glyph's zigzag is not)
        if is_strong and gap <= max(reach, CLOSE_GAP_SHARE * length) and length >= CLOSE_MIN_MM * ppm and len(px) >= 4:
            # Its ends meet: an outline, drawn as areas are drawn — a loop with one gap.
            mark['kind'] = 'polygon'
        if not is_strong:
            mark['weak'] = True   # glyph-sized and alone: writing, unless the model's mark lies on it
        out.append(mark)
    return out


def _take_hatched(comps, shape, ppm, out):
    """Clusters of several short strokes within HATCH_DILATE_MM of each other are
    hatched areas: appended to `out` as 'spraycan' marks (the ink pixels,
    subsampled); the remaining components are returned."""
    if not comps:
        return comps
    index = np.full(shape, -1, dtype=np.int32)
    for i, blob in enumerate(comps):
        for y, x in blob:
            index[y, x] = i
    grown = index >= 0
    for _ in range(int(round(HATCH_DILATE_MM * ppm))):
        grown = _dilate(grown)
    max_stroke = HATCH_MAX_STROKE_MM * ppm
    min_stroke = HATCH_MIN_STROKE_MM * ppm
    used = set()
    for cluster in _components(grown):
        members = sorted({int(index[y, x]) for y, x in cluster if index[y, x] >= 0})
        members = [i for i in members if _extent(comps[i]) >= min_stroke]   # specks say nothing
        small = [i for i in members if _extent(comps[i]) <= max_stroke]
        if len(small) < HATCH_MIN_STROKES or len(small) < 0.7 * len(members):
            continue
        ys = [p[0] for p in cluster]
        xs = [p[1] for p in cluster]
        if max(max(xs) - min(xs), max(ys) - min(ys)) < 2 * max_stroke:
            continue   # a label of a few glyphs, not an area
        px = []
        for i in small:
            for y, x in comps[i]:
                if y % SPRAY_STEP_PX == 0 and x % SPRAY_STEP_PX == 0:
                    px.append((x, y))
            used.add(i)
        out.append({'kind': 'spraycan', 'px': px, 'bbox': (min(xs), min(ys), max(xs), max(ys)), 'area': len(cluster)})
    return [c for i, c in enumerate(comps) if i not in used]


def _extent(blob):
    ys = [p[0] for p in blob]
    xs = [p[1] for p in blob]
    return max(max(xs) - min(xs), max(ys) - min(ys)) + 1


# ── morphology on boolean arrays ───────────────────────────────────────────

def _erode(m):
    out = m.copy()
    out[1:, :] &= m[:-1, :]
    out[:-1, :] &= m[1:, :]
    out[:, 1:] &= m[:, :-1]
    out[:, :-1] &= m[:, 1:]
    return out


def _dilate(m):
    out = m.copy()
    out[1:, :] |= m[:-1, :]
    out[:-1, :] |= m[1:, :]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def _open(m):
    return _dilate(_erode(m))


def _close(m, r):
    for _ in range(r):
        m = _dilate(m)
    for _ in range(r):
        m = _erode(m)
    return m


def _local_mean(a, window):
    """Mean of `a` over a window×window box around every pixel (edges replicated)."""
    r = window // 2
    padded = np.pad(a, r, mode='edge')
    return texture._window_sums(padded, window, window) / float(window * window)


def _local_min(a, r):
    """Minimum of `a` over the (2r+1)² box around every pixel (edges replicated)."""
    padded = np.pad(a, r, mode='edge')
    h, w = a.shape
    out = padded[r:r + h, r:r + w].copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out = np.minimum(out, padded[r + dy:r + dy + h, r + dx:r + dx + w])
    return out


def _components(mask):
    """4-connected components of a boolean array, as lists of (y, x)."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            blob, stack = [], [(y, x)]
            seen[y, x] = True
            while stack:
                cy, cx = stack.pop()
                blob.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            out.append(blob)
    return out


def _fill_holes(crop):
    """(the component with its holes filled, hole area): the background is
    flooded from the crop's border; what it cannot reach is inside."""
    h, w = crop.shape
    reached = np.zeros_like(crop)
    stack = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    for y, x in stack:
        reached[y, x] = not crop[y, x]
    stack = [p for p in stack if reached[p]]
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not crop[ny, nx] and not reached[ny, nx]:
                reached[ny, nx] = True
                stack.append((ny, nx))
    holes = ~crop & ~reached
    return crop | holes, int(holes.sum())


def _thin(crop):
    """Zhang–Suen thinning: the one-pixel skeleton of a boolean array."""
    img = crop.copy()
    img[0, :] = img[-1, :] = img[:, 0] = img[:, -1] = False
    while True:
        changed = False
        for step in (0, 1):
            p = img
            p2 = np.roll(p, 1, 0)
            p3 = np.roll(np.roll(p, 1, 0), -1, 1)
            p4 = np.roll(p, -1, 1)
            p5 = np.roll(np.roll(p, -1, 0), -1, 1)
            p6 = np.roll(p, -1, 0)
            p7 = np.roll(np.roll(p, -1, 0), 1, 1)
            p8 = np.roll(p, 1, 1)
            p9 = np.roll(np.roll(p, 1, 0), 1, 1)
            ring = [p2, p3, p4, p5, p6, p7, p8, p9]
            b = sum(r.astype(np.int8) for r in ring)
            a = sum(((~ring[i]) & ring[(i + 1) % 8]).astype(np.int8) for i in range(8))
            if step == 0:
                cond = (~(p2 & p4 & p6)) & (~(p4 & p6 & p8))
            else:
                cond = (~(p2 & p4 & p8)) & (~(p2 & p6 & p8))
            remove = p & (b >= 2) & (b <= 6) & (a == 1) & cond
            if remove.any():
                img = img & ~remove
                changed = True
        if not changed:
            return img


def _longest_path(skeleton):
    """The longest end-to-end walk of a skeleton as [(y, x)], from the farthest
    endpoint to the farthest point from it (twice BFS; spurs are left out)."""
    pts = list(zip(*np.nonzero(skeleton)))
    if not pts:
        return []
    on = set(pts)

    def neighbours(p):
        y, x = p
        return [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy or dx) and (y + dy, x + dx) in on]

    def farthest(start):
        prev = {start: None}
        queue = [start]
        last = start
        while queue:
            nxt = []
            for p in queue:
                for q in neighbours(p):
                    if q not in prev:
                        prev[q] = p
                        nxt.append(q)
            if nxt:
                last = nxt[-1]
            queue = nxt
        return last, prev
    ends = [p for p in pts if len(neighbours(p)) == 1]
    a, _ = farthest(ends[0] if ends else pts[0])
    b, prev = farthest(a)
    path = []
    while b is not None:
        path.append(b)
        b = prev[b]
    return path[::-1]


def _trace_boundary(filled):
    """The outer boundary of a filled shape as [(y, x)], Moore-neighbour tracing."""
    h, w = filled.shape
    start = None
    for y in range(h):
        row = np.nonzero(filled[y])[0]
        if len(row):
            start = (y, int(row[0]))
            break
    if start is None:
        return []
    moves = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]
    ring = [start]
    cur = start
    back = 6   # came from the west (index of the move pointing west... start looking north-west)
    for _ in range(4 * (h + w) + len(np.nonzero(filled)[0]) * 2):
        found = False
        for k in range(8):
            d = (back + k) % 8
            ny, nx = cur[0] + moves[d][0], cur[1] + moves[d][1]
            if 0 <= ny < h and 0 <= nx < w and filled[ny, nx]:
                cur = (ny, nx)
                back = (d + 5) % 8   # start next search just after the direction we came from
                found = True
                break
        if not found:
            break
        if cur == start:
            break
        ring.append(cur)
    return ring


def _simplify(points, tolerance):
    """Douglas–Peucker over [(x, y)]."""
    if len(points) < 3:
        return list(points)
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5
    best, index = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        dist = abs(dx * (y1 - py) - dy * (x1 - px)) / norm if norm else ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        if dist > best:
            best, index = dist, i
    if best > tolerance:
        left = _simplify(points[:index + 1], tolerance)
        right = _simplify(points[index:], tolerance)
        return left[:-1] + right
    return [points[0], points[-1]]
