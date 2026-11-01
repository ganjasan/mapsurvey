"""Landmarks INSIDE the map frame, from the printed map itself (item 4).

The fiducials and the frame's border register the photo at the edge of the map.
A page bowed in a hand lifts the middle of the map towards the camera, and the
middle then projects somewhere the border cannot tell — on one lap shot a dot
6 mm from the bottom edge was 5.5 mm off with the border matched to 0.3 mm.
The only thing inside the frame whose place on the paper is known is the map
that was printed there, and that image we have (saved at print time, else
re-rendered from the same frame spec). So: rectify the photo's frame into the
reference's pixel grid through the border registration, slide reference
patches over it at a grid of anchors (normalised cross-correlation, numpy), and
every clear peak is one more landmark — photo pixel ↔ page millimetre — for the
fit and its bend correction.
"""
import io
import logging

import numpy as np
from PIL import Image

from survey.paper import marks

log = logging.getLogger('survey.paper')

GRID = (6, 4)          # anchors across × down the frame, the outer ones MARGIN in from the border
MARGIN = 0.08          # of the frame's width/height kept clear at the edges (half a patch)
PATCH = 64             # reference pixels (the reference is ~5 px/mm)
SEARCH = 28            # ± pixels around the predicted place (≈ ±5.5 mm)
MIN_PEAK = 0.35        # normalised cross-correlation of an accepted match
MIN_PROMINENCE = 0.15  # peak above the median of the correlation surface
REF_WIDTH = 900        # reference image width in px (FRAME_W): 5 px/mm on a 180-mm frame


def reference_key(form_pk, page_number):
    """Where the printed frame of a form's page is kept, on the PRIVATE tier."""
    return f'paper_refs/{form_pk}-{page_number}.png'


def save_reference(form_pk, page_number, image):
    """Keep what was printed — `image` is the frame as `static_map.render_frame`
    gave it — for the photos that will come back: a reference layer edited after
    the print (objects on a published survey are live) would otherwise make a
    re-render that no longer matches the paper. Returns the storage key."""
    from django.core.files.base import ContentFile

    from survey.models import _private_media_storage
    buf = io.BytesIO()
    _normalise(image).save(buf, format='PNG', optimize=True)
    storage = _private_media_storage()
    key = reference_key(form_pk, page_number)
    if storage.exists(key):
        storage.delete(key)   # a reprint of the same form row: the newest print wins
    return storage.save(key, ContentFile(buf.getvalue()))


def reference_image(page):
    """The printed frame of this page as a grayscale Pillow image REF_WIDTH wide,
    or None: the PNG saved at print time, else a fresh render of the same frame
    (forms printed before the reference was kept)."""
    rec = ((page.printed_form.layout or {}).get(str(page.page_number)) or {}).get('map') if page.printed_form_id else None
    if not rec:
        return None
    key = rec.get('ref_key')
    if key:
        try:
            from survey.models import _private_media_storage
            with _private_media_storage().open(key, 'rb') as fh:
                img = Image.open(io.BytesIO(fh.read()))
                img.load()
                return _normalise(img)
        except Exception:  # noqa: BLE001 — a lost file falls back to a render
            log.warning('paper: reference image %s unreadable, re-rendering', key)
    try:
        from survey.models import SurveySection
        from survey.paper.extract import version_header
        from survey.print import static_map
        header = version_header(page.printed_form)
        section = SurveySection.objects.filter(survey_header=header, code=rec.get('section_code')).first()
        if section is None:
            return None
        frame = static_map.render_frame(section, header)
        if not frame.basemap_ok:
            return None
        return _normalise(frame.image)
    except Exception:  # noqa: BLE001 — no reference is "no interior landmarks", never a failed read
        log.warning('paper: could not render the reference frame for page %s', page.pk, exc_info=True)
        return None


def _normalise(img):
    img = img.convert('L')
    if img.width != REF_WIDTH:
        img = img.resize((REF_WIDTH, max(1, round(img.height * REF_WIDTH / img.width))), Image.BILINEAR)
    return img


def interior_landmarks(photo_gray, reg, map_rec, ref):
    """[(photo px, page mm, shift px)] at the grid anchors whose reference patch
    is found on the photo rectified through `reg` (plane + spline — so a second
    round, with the registration the first round informed, finds the bend the
    first window clipped). `photo_gray` is the full-resolution grayscale page;
    `shift` is how far from `reg`'s prediction the match was, in reference px."""
    ref_a = np.asarray(ref, dtype=np.float32)
    rh_px, rw_px = ref_a.shape
    ppm = rw_px / float(map_rec['w_mm'])          # reference pixels per mm
    rx, ry = map_rec['x_mm'], map_rec['y_mm']
    pad = SEARCH + PATCH
    maps = _inverse_maps(reg, rx, ry, ppm, -pad, rw_px + pad, -pad, rh_px + pad)
    if maps is None:
        return []
    px_x, px_y = maps
    photo = np.asarray(photo_gray, dtype=np.float32)
    rect = _bilinear(photo, px_x, px_y)
    out = []
    cols, rows = GRID
    half = PATCH // 2
    for j in range(rows):
        for i in range(cols):
            au = int(round((MARGIN + (1 - 2 * MARGIN) * i / (cols - 1)) * rw_px))
            av = int(round((MARGIN + (1 - 2 * MARGIN) * j / (rows - 1)) * rh_px))
            patch = ref_a[av - half:av + half, au - half:au + half]
            if patch.shape != (PATCH, PATCH) or patch.std() < 6:
                continue   # a blank piece of map says nothing
            # In the rectified image, reference (u, v) sits at (u + pad, v + pad).
            region = rect[av + pad - half - SEARCH:av + pad + half + SEARCH,
                          au + pad - half - SEARCH:au + pad + half + SEARCH]
            if region.shape != (PATCH + 2 * SEARCH, PATCH + 2 * SEARCH):
                continue
            surface = _ncc(patch, region)
            peak = float(surface.max())
            if peak < MIN_PEAK or peak - float(np.median(surface)) < MIN_PROMINENCE:
                continue
            dy, dx = np.unravel_index(int(surface.argmax()), surface.shape)
            dx, dy = int(dx) - SEARCH, int(dy) - SEARCH
            if max(abs(dx), abs(dy)) >= SEARCH - 1:
                continue   # a peak on the window's rim is the window, not a match
            # The content printed at anchor A shows up d pixels away in the
            # rectified photo: the photo pixel of A is what was sampled there.
            src = (float(px_x[av + dy + pad, au + dx + pad]), float(px_y[av + dy + pad, au + dx + pad]))
            out.append((src, (rx + au / ppm, ry + av / ppm), max(abs(dx), abs(dy))))
    return out


def _stretch(a):
    lo, hi = np.percentile(a, 2), np.percentile(a, 98)
    return np.clip((a - lo) / max(float(hi - lo), 1.0) * 255.0, 0, 255)


INVERSE_STRIDE = 4   # the inverse of the registration is smooth: solve it every 4 px, interpolate between


def _inverse_maps(reg, rx, ry, ppm, u0, u1, v0, v1):
    """Photo pixel (x, y) for every reference pixel in [u0, u1) × [v0, v1):
    the plane's inverse, corrected for the spline by fixed-point iteration on a
    coarse grid (reg(p) = plane(p) + tps(p) = mm ⇒ p = plane⁻¹(mm − tps(p)))."""
    h = reg['h'] if isinstance(reg, dict) else reg
    tps = reg.get('tps') if isinstance(reg, dict) else None
    inv = marks._invert3(h)
    if inv is None:
        return None

    def plane_inv(mx, my):
        den = inv[2][0] * mx + inv[2][1] * my + inv[2][2]
        return ((inv[0][0] * mx + inv[0][1] * my + inv[0][2]) / den,
                (inv[1][0] * mx + inv[1][1] * my + inv[1][2]) / den)

    s = INVERSE_STRIDE
    cu = np.arange(u0, u1 + s, s, dtype=np.float32)
    cv = np.arange(v0, v1 + s, s, dtype=np.float32)
    CU, CV = np.meshgrid(cu, cv)
    mm_x, mm_y = rx + CU / ppm, ry + CV / ppm
    px, py = plane_inv(mm_x, mm_y)
    if tps:
        for _ in range(4):
            cx, cy = _tps_np(tps, px, py)
            px, py = plane_inv(mm_x - cx, mm_y - cy)
    U, V = np.meshgrid(np.arange(u0, u1, dtype=np.float32), np.arange(v0, v1, dtype=np.float32))
    fx, fy = (U - u0) / s, (V - v0) / s
    return _bilinear(px.astype(np.float32), fx, fy), _bilinear(py.astype(np.float32), fx, fy)


def _tps_np(tps, x, y):
    """marks._tps_value over arrays."""
    sx, sy = x / tps['scale'], y / tps['scale']
    out = []
    for axis in 'xy':
        a = tps['a' + axis]
        v = a[0] + a[1] * sx + a[2] * sy
        for (px_, py_), wgt in zip(tps['pts'], tps['w' + axis]):
            r2 = (sx - px_) ** 2 + (sy - py_) ** 2
            v = v + wgt * r2 * np.log(np.where(r2 > 0, r2, 1.0))
        out.append(v)
    return out[0], out[1]


def _bilinear(a, x, y):
    """Sample image `a` at float coordinates (x, y); outside → 0."""
    h, w = a.shape
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = x - x0
    fy = y - y0
    inside = (x0 >= 0) & (x0 < w - 1) & (y0 >= 0) & (y0 < h - 1)
    x0c = np.clip(x0, 0, w - 2)
    y0c = np.clip(y0, 0, h - 2)
    v = (a[y0c, x0c] * (1 - fx) * (1 - fy) + a[y0c, x0c + 1] * fx * (1 - fy)
         + a[y0c + 1, x0c] * (1 - fx) * fy + a[y0c + 1, x0c + 1] * fx * fy)
    return np.where(inside, v, 0.0).astype(np.float32)


def _ncc(patch, region):
    """Normalised cross-correlation of `patch` over every position of `region`:
    the cross-correlation through the FFT, each window's mean and variance
    through summed-area tables (a sliding-window view costs 50× as much)."""
    ph, pw = patch.shape
    rh, rw = region.shape
    n = float(ph * pw)
    p = patch - patch.mean()
    pn = float(np.sqrt((p * p).sum())) or 1.0
    corr = np.fft.irfft2(np.fft.rfft2(region) * np.fft.rfft2(p[::-1, ::-1], s=region.shape), s=region.shape)
    corr = corr[ph - 1:rh, pw - 1:rw]
    sums = _window_sums(region, ph, pw)
    sq = _window_sums(region * region, ph, pw)
    var = sq - sums * sums / n
    norms = np.sqrt(np.where(var > 1e-6, var, 1e-6))
    return corr / (norms * pn)


def _window_sums(a, ph, pw):
    """Sum of every ph×pw window of `a`, via a summed-area table."""
    table = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.float64)
    table[1:, 1:] = np.cumsum(np.cumsum(a, axis=0, dtype=np.float64), axis=1)
    return table[ph:, pw:] - table[:-ph, pw:] - table[ph:, :-pw] + table[:-ph, :-pw]
