/* L.SprayLayer — one cloud of sprayed dots on one canvas (spec spraycan-question).
 *
 * A `spraycan` answer is a MultiPoint of up to tens of thousands of dots. One
 * Leaflet marker per dot is out of the question, so the cloud is a single
 * L.Layer that owns a <canvas> in the overlay pane and STAMPS every dot the way
 * a graphics editor's airbrush does: one pre-rendered sprite (a soft radial
 * halo with a hard grain in the middle) drawn with drawImage, so overlapping
 * dots accumulate into solid paint and the edge of a cloud stays soft. A
 * sprite blit is GPU work; tens of thousands redraw in a few frames on a
 * budget phone, and while a stroke is being painted only the new dots are
 * drawn (nothing is redrawn until the map stops moving).
 *
 * It behaves like the other answer layers where the respondent page expects it
 * to: `feature`/`toGeoJSON()` (a Feature<MultiPoint>, so the HTMX serializer
 * and `_geoLayersFor` need no special case), `bindPopup`/`openPopup` (anchored
 * at `getCenter()`), a no-op `editing` object (editing a cloud means re-entering
 * paint mode, never Leaflet.draw's vertex editing), `getBounds()`.
 *
 * Shared by the respondent map, the Responses drawer/modal and the editor
 * preview — the one place the dots are drawn.
 */
(function () {
    'use strict';
    if (typeof L === 'undefined') { return; }

    L.SprayLayer = L.Layer.extend({
        options: {
            color: '#000000',
            haloRadius: 6,      // screen px — the soft stamp around each dot
            haloOpacity: 0.16,  // accumulates: ~6 overlapping stamps read as solid
            grainRadius: 1.3,   // the hard speck in the middle (Paint's "dust")
            grainOpacity: 0.85,
            pane: 'overlayPane',
            interactive: true   // click on a dot opens the popup
        },

        initialize: function (latlngs, options) {
            L.setOptions(this, options);
            this._dots = [];
            this.setDots(latlngs || []);
        },

        // ----- data -----------------------------------------------------
        setDots: function (latlngs) {
            this._dots = [];
            for (var i = 0; i < latlngs.length; i++) { this._dots.push(L.latLng(latlngs[i])); }
            this.redraw();
            return this;
        },
        getDots: function () { return this._dots.slice(); },
        count: function () { return this._dots.length; },
        clear: function () { this._dots = []; this.redraw(); return this; },

        // Append dots and paint only them — a stroke adds a handful at a time,
        // a full redraw per tick would be wasteful on a phone.
        addDots: function (latlngs) {
            if (!latlngs.length) { return this; }
            var start = this._dots.length;
            for (var i = 0; i < latlngs.length; i++) { this._dots.push(L.latLng(latlngs[i])); }
            if (this._map && this._ctx) { this._paint(start); }
            return this;
        },

        // Remove every dot within `px` screen pixels of a container point.
        eraseNear: function (containerPoint, px) {
            if (!this._map) { return 0; }
            var keep = [], removed = 0, r2 = px * px;
            for (var i = 0; i < this._dots.length; i++) {
                var p = this._map.latLngToContainerPoint(this._dots[i]);
                var dx = p.x - containerPoint.x, dy = p.y - containerPoint.y;
                if (dx * dx + dy * dy <= r2) { removed++; } else { keep.push(this._dots[i]); }
            }
            if (removed) { this._dots = keep; this.redraw(); }
            return removed;
        },

        // True when a dot lies within `px` screen pixels of the latlng.
        hitTest: function (latlng, px) {
            if (!this._map) { return false; }
            var c = this._map.latLngToContainerPoint(latlng), r2 = px * px;
            // Quick reject: the cloud's bounds, padded by the hit radius.
            if (this._dots.length > 64) {
                var b = this.getBounds();
                if (b.isValid()) {
                    var sw = this._map.latLngToContainerPoint(b.getSouthWest());
                    var ne = this._map.latLngToContainerPoint(b.getNorthEast());
                    if (c.x < Math.min(sw.x, ne.x) - px || c.x > Math.max(sw.x, ne.x) + px ||
                        c.y < Math.min(sw.y, ne.y) - px || c.y > Math.max(sw.y, ne.y) + px) { return false; }
                }
            }
            for (var i = 0; i < this._dots.length; i++) {
                var p = this._map.latLngToContainerPoint(this._dots[i]);
                var dx = p.x - c.x, dy = p.y - c.y;
                if (dx * dx + dy * dy <= r2) { return true; }
            }
            return false;
        },

        getBounds: function () { return L.latLngBounds(this._dots); },

        // Mean of the dots: where the popup anchors and what selection tests.
        getCenter: function () {
            var n = this._dots.length;
            if (!n) { return this._map ? this._map.getCenter() : L.latLng(0, 0); }
            var lat = 0, lng = 0;
            for (var i = 0; i < n; i++) { lat += this._dots[i].lat; lng += this._dots[i].lng; }
            return L.latLng(lat / n, lng / n);
        },
        getLatLng: function () { return this.getCenter(); },

        toGeoJSON: function (precision) {
            var p = precision === undefined ? 6 : precision;
            var coords = [];
            for (var i = 0; i < this._dots.length; i++) {
                coords.push([L.Util.formatNum(this._dots[i].lng, p), L.Util.formatNum(this._dots[i].lat, p)]);
            }
            return L.GeoJSON.getFeature(this, { type: 'MultiPoint', coordinates: coords });
        },

        setStyle: function (style) {
            L.setOptions(this, style);
            this._sprite = null;
            this.redraw();
            return this;
        },

        // One sprite per layer (per colour, per device pixel ratio): a radial
        // gradient halo fading to transparent, a near-opaque grain at the
        // centre. Rebuilt only when the style changes.
        _getSprite: function () {
            var ratio = window.devicePixelRatio || 1;
            if (this._sprite && this._sprite.ratio === ratio) { return this._sprite; }
            var r = this.options.haloRadius, size = Math.ceil(r * 2 + 2);
            var c = document.createElement('canvas');
            c.width = c.height = Math.ceil(size * ratio);
            var ctx = c.getContext('2d');
            ctx.scale(ratio, ratio);
            var cx = size / 2, cy = size / 2;
            var g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
            var rgb = this._rgb(this.options.color);
            g.addColorStop(0, 'rgba(' + rgb + ',' + this.options.haloOpacity + ')');
            g.addColorStop(0.55, 'rgba(' + rgb + ',' + (this.options.haloOpacity * 0.5) + ')');
            g.addColorStop(1, 'rgba(' + rgb + ',0)');
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, size, size);
            ctx.globalAlpha = this.options.grainOpacity;
            ctx.fillStyle = this.options.color;
            ctx.beginPath();
            ctx.arc(cx, cy, this.options.grainRadius, 0, Math.PI * 2);
            ctx.fill();
            this._sprite = { canvas: c, size: size, half: size / 2, ratio: ratio };
            return this._sprite;
        },

        _rgb: function (hex) {
            var m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
            if (!m) { return '0,0,0'; }
            var n = parseInt(m[1], 16);
            return ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255);
        },

        // ----- Leaflet plumbing -----------------------------------------
        onAdd: function (map) {
            this._canvas = L.DomUtil.create('canvas', 'leaflet-spray-layer');
            this._canvas.style.pointerEvents = 'none';
            this._ctx = this._canvas.getContext('2d');
            this.getPane().appendChild(this._canvas);
            if (this.options.interactive) { map.on('click', this._onMapClick, this); }
            this.redraw();
        },
        onRemove: function (map) {
            if (this.options.interactive) { map.off('click', this._onMapClick, this); }
            L.DomUtil.remove(this._canvas);
            this._canvas = null;
            this._ctx = null;
        },
        getEvents: function () {
            // No `move`: the canvas sits in the overlay pane and travels with it
            // during a drag; redrawing every frame is what would make a big
            // cloud stutter on a phone. One redraw when the move settles.
            return {
                moveend: this.redraw,
                viewreset: this.redraw,
                resize: this.redraw,
                zoomstart: this._hide,
                zoomend: this._show
            };
        },

        _hide: function () { if (this._canvas) { this._canvas.style.visibility = 'hidden'; } },
        _show: function () { if (this._canvas) { this._canvas.style.visibility = ''; this.redraw(); } },

        // Place the canvas over the current viewport and paint every dot.
        redraw: function () {
            if (!this._map || !this._canvas) { return this; }
            var size = this._map.getSize();
            var ratio = window.devicePixelRatio || 1;
            if (this._canvas.width !== size.x * ratio || this._canvas.height !== size.y * ratio) {
                this._canvas.width = size.x * ratio;
                this._canvas.height = size.y * ratio;
                this._canvas.style.width = size.x + 'px';
                this._canvas.style.height = size.y + 'px';
            }
            L.DomUtil.setPosition(this._canvas, this._map.containerPointToLayerPoint([0, 0]));
            this._ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
            this._ctx.clearRect(0, 0, size.x, size.y);
            this._paint(0);
            return this;
        },

        _paint: function (from) {
            var ctx = this._ctx, map = this._map;
            if (!ctx || !map) { return; }
            var s = this._getSprite(), half = s.half, size = s.size, img = s.canvas;
            for (var i = from; i < this._dots.length; i++) {
                var p = map.latLngToContainerPoint(this._dots[i]);
                ctx.drawImage(img, p.x - half, p.y - half, size, size);
            }
        },

        // A click on paint opens the popup, like a click on a marker. Paint
        // mode owns the pointer and sets `map._sprayPaintActive` while it runs.
        _onMapClick: function (e) {
            if (!this._map || this._map._sprayPaintActive) { return; }
            if (!this.hitTest(e.latlng, Math.max(this.options.haloRadius * 2, 12))) { return; }
            L.DomEvent.stop(e.originalEvent);
            this.fire('click', { latlng: this.getCenter(), originalEvent: e.originalEvent });
        },

        // Leaflet.draw-style editing does not apply; the popup code calls
        // `editing.disable()` on every layer, so it must exist.
        editing: { enable: function () {}, disable: function () {}, enabled: function () { return false; } }
    });

    L.sprayLayer = function (latlngs, options) { return new L.SprayLayer(latlngs, options); };

    // Airbrush scatter: a 2-D Gaussian centred on the pointer (sigma = r/2.2),
    // clipped to the brush ring, so the centre is dense and the edge thins out
    // — Krita's and GIMP's airbrush distribution, not a uniform stencil.
    L.SprayLayer.scatter = function (containerPoint, r, n) {
        var out = [], sigma = r / 2.2;
        for (var i = 0; i < n; i++) {
            var dx, dy, tries = 0;
            do {
                var u = Math.random() || 1e-9, v = Math.random();
                var mag = Math.sqrt(-2 * Math.log(u)), ang = 2 * Math.PI * v;
                dx = sigma * mag * Math.cos(ang); dy = sigma * mag * Math.sin(ang);
            } while (dx * dx + dy * dy > r * r && ++tries < 8);
            out.push(L.point(containerPoint.x + dx, containerPoint.y + dy));
        }
        return out;
    };
})();

/* L.SprayAgreementLayer — many clouds (or shapes), one surface
 * (specs spraycan-density-views, responses-coverage-surface).
 *
 * What the Responses map and the Overview thumbnail show for a spraycan
 * question, and what a Coverage layer shows over a line or polygon question:
 * for every cell, the SHARE of respondents whose cloud touches it — or whose
 * polygon contains it, or whose line passes within `corridorMeters` of it. Every respondent counts once whatever their dot count, a lone respondent
 * paints a flat full-strength area, and ten respondents who agree paint a dark
 * core with light fringes — the same statistic the public page publishes as a
 * grid. (leaflet.heat was tried first: it scales intensity by 2^(maxZoom-zoom),
 * so every cell sat on the opacity floor and the surface came out flat.)
 *
 * Cost: one pass over the dots per redraw (binning), then ONE drawImage of a
 * cell-sized offscreen canvas scaled up with bilinear smoothing — which is also
 * what makes the surface soft without a blur filter. Redraws on moveend/zoomend
 * only; the canvas rides the overlay pane during a drag.
 */
(function () {
    'use strict';
    if (typeof L === 'undefined') { return; }

    L.SprayAgreementLayer = L.Layer.extend({
        options: {
            // style 'grid' (default, owner's pick 2026-10-04): the public page's
            // look — crisp geographic cells in one colour, opacity by the share of
            // respondents. style 'heat': the same share through a heat ramp with a
            // soft fringe.
            style: 'grid',
            color: '#d6336c',
            // Grid cells are GEOGRAPHIC (metres), anchored to the world like the
            // server grid, so they do not slide when the map pans and the creator
            // sees the same cells the public page publishes. null = derive from
            // the clouds' extent exactly as public_results_grid does.
            cellMeters: null,
            cellsAcross: 40, minCellMeters: 20,
            corridorMeters: 20,  // shapes: a line covers the cells within this distance (one urban street)
            cellPx: 6,          // 'heat' style: screen px per cell; smoothing hides the grid
            blur: 2,            // 'heat' style: box-blur radius in cells
            minAlpha: 0.15,     // any painted cell stays visible
            maxAlpha: 0.75,     // every respondent agrees
            gradient: { 0.0: '#3b82f6', 0.35: '#06b6d4', 0.55: '#84cc16', 0.75: '#facc15', 1.0: '#ef4444' },
            pane: 'overlayPane'
        },

        // members: [{ id, dots: [[lat, lng], ...] }] — spray clouds — or
        //          [{ id, geometry: <GeoJSON LineString|Polygon|Multi*> }] — drawn
        //          shapes (change responses-coverage-surface). One id = one
        //          respondent; a shape covers the cells inside it (polygons, holes
        //          excluded) or within `corridorMeters` of it (lines).
        initialize: function (members, options) {
            L.setOptions(this, options);
            this._clouds = members || [];
            this._active = null;   // Set of ids, or null = all
            this._stats = { max: 0, respondents: 0 };
        },
        setClouds: function (members) { this._clouds = members || []; this._cellM = null; this.redraw(); return this; },
        setMembers: function (members) { return this.setClouds(members); },
        setFilter: function (ids) { this._active = ids || null; this.redraw(); return this; },
        setStyle: function (style) { L.setOptions(this, style); this._rgb = null; this._ramp = null; this.redraw(); return this; },
        // {max, respondents} of the last redraw: the highest count in any cell
        // and the members in scope. Fired as a 'stats' event after each redraw.
        getStats: function () { return this._stats; },

        getBounds: function () {
            var b = L.latLngBounds([]);
            var walk = function (coords) {
                if (typeof coords[0] === 'number') { b.extend([coords[1], coords[0]]); return; }
                for (var i = 0; i < coords.length; i++) { walk(coords[i]); }
            };
            this._clouds.forEach(function (c) {
                if (c.dots) { c.dots.forEach(function (d) { b.extend(d); }); }
                else if (c.geometry && c.geometry.coordinates) { walk(c.geometry.coordinates); }
            });
            return b;
        },

        onAdd: function () {
            this._canvas = L.DomUtil.create('canvas', 'leaflet-spray-layer');
            this._canvas.style.pointerEvents = 'none';
            this._ctx = this._canvas.getContext('2d');
            this._cells = document.createElement('canvas');
            this.getPane().appendChild(this._canvas);
            this.redraw();
        },
        onRemove: function () { L.DomUtil.remove(this._canvas); this._canvas = null; this._ctx = null; },
        getEvents: function () {
            return { moveend: this.redraw, viewreset: this.redraw, resize: this.redraw,
                     zoomstart: this._hide, zoomend: this._show };
        },
        _hide: function () { if (this._canvas) { this._canvas.style.visibility = 'hidden'; } },
        _show: function () { if (this._canvas) { this._canvas.style.visibility = ''; this.redraw(); } },

        redraw: function () {
            if (!this._map || !this._canvas) { return this; }
            var map = this._map, size = map.getSize(), cell = this.options.cellPx;
            if (!(size.x > 0 && size.y > 0)) { return this; }   // Map pane still hidden: nothing to measure against
            var ratio = window.devicePixelRatio || 1;
            if (this._canvas.width !== size.x * ratio || this._canvas.height !== size.y * ratio) {
                this._canvas.width = size.x * ratio; this._canvas.height = size.y * ratio;
                this._canvas.style.width = size.x + 'px'; this._canvas.style.height = size.y + 'px';
            }
            L.DomUtil.setPosition(this._canvas, map.containerPointToLayerPoint([0, 0]));
            var ctx = this._ctx;
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
            if (this.options.style === 'grid') { return this._redrawGrid(ctx, size, ratio); }

            // Bin: cell -> number of members. Cells one step outside the view are
            // kept so the smoothing has neighbours at the edges.
            var cols = Math.ceil(size.x / cell) + 2, rows = Math.ceil(size.y / cell) + 2;
            var range = { x0: -1, y0: -1, x1: cols - 1, y1: rows - 1 };
            var lat = map.getCenter().lat;
            var corridorCells = this.options.corridorMeters / this._metersPerPixel(lat, map.getZoom()) / cell;
            var bins = this._bin(function (ll) { return map.latLngToContainerPoint(ll); }, cell, range, corridorCells);
            var hits = bins.hits, n = bins.n;
            if (!n || !hits.size) { return this; }

            // Agreement per cell (0..1), then a box blur so the surface falls
            // off softly past the painted cells instead of stopping dead.
            var share = new Float32Array(cols * rows);
            hits.forEach(function (count, key) { share[key] = count / n; });
            var field = this._blur(share, cols, rows, this.options.blur);

            // One pixel per cell: colour from the ramp, alpha from the share;
            // scaled up with bilinear smoothing.
            var cells = this._cells;
            cells.width = cols; cells.height = rows;
            var cctx = cells.getContext('2d');
            var img = cctx.createImageData(cols, rows), data = img.data;
            var ramp = this.options.gradient ? this._rampOf(this.options.gradient) : null;
            var rgb = this._rgbOf(this.options.color);
            var lo = this.options.minAlpha, hi = this.options.maxAlpha;
            for (var k = 0; k < field.length; k++) {
                var v = field[k];
                if (v <= 0.002) { continue; }
                var o = k * 4;
                if (ramp) {
                    var ri = Math.min(255, Math.round(v * 255)) * 3;
                    data[o] = ramp[ri]; data[o + 1] = ramp[ri + 1]; data[o + 2] = ramp[ri + 2];
                } else {
                    data[o] = rgb[0]; data[o + 1] = rgb[1]; data[o + 2] = rgb[2];
                }
                // Blurred fringe fades out; painted cells sit between minAlpha and maxAlpha.
                var a = v >= 1 / n ? lo + (hi - lo) * Math.min(1, v) : (v * n) * lo;
                data[o + 3] = Math.round(Math.min(1, a) * 255);
            }
            cctx.putImageData(img, 0, 0);
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(cells, -cell * ratio, -cell * ratio, cols * cell * ratio, rows * cell * ratio);
            return this;
        },

        // ── binning (one seam for clouds and shapes) ─────────────────────
        // Counts members per cell over the cell grid defined by `project`
        // (latlng -> pixel point) and `cellPx`, restricted to `range`
        // {x0, y0, x1, y1} in cell units (x1/y1 exclusive). Keys are row-major
        // indices into the range; every member counts once per cell. Also
        // records the stats and fires 'stats'.
        _bin: function (project, cellPx, range, corridorCells) {
            var hits = new Map(), n = 0, max = 0;
            var w = range.x1 - range.x0;
            var add = function (key) {
                var c = (hits.get(key) || 0) + 1;
                hits.set(key, c);
                if (c > max) { max = c; }
            };
            for (var i = 0; i < this._clouds.length; i++) {
                var m = this._clouds[i];
                if (this._active && !this._active.has(m.id)) { continue; }
                if (m.dots) {
                    if (!m.dots.length) { continue; }
                    n++;
                    var seen = new Set();
                    for (var j = 0; j < m.dots.length; j++) {
                        var p = project(m.dots[j]);
                        var cx = Math.floor(p.x / cellPx), cy = Math.floor(p.y / cellPx);
                        if (cx < range.x0 || cy < range.y0 || cx >= range.x1 || cy >= range.y1) { continue; }
                        var key = (cy - range.y0) * w + (cx - range.x0);
                        if (seen.has(key)) { continue; }
                        seen.add(key);
                        add(key);
                    }
                } else if (m.geometry && m.geometry.coordinates && m.geometry.coordinates.length) {
                    n++;
                    this._rasterise(m.geometry, project, cellPx, range, corridorCells, add);
                }
            }
            this._stats = { max: max, respondents: n };
            this.fire('stats', this._stats);
            return { hits: hits, n: n };
        },

        // A shape's covered cells: draw it onto an offscreen canvas whose pixel
        // grid IS the cell grid (one pixel per cell), clipped to the shape's
        // bounding box within `range`, and read the alpha channel back — the
        // browser's rasteriser handles any ring count, holes (even-odd fill)
        // and the line corridor (stroke width in cells) natively, and the
        // precision is one cell, which is the resolution of the statistic.
        _rasterise: function (geometry, project, cellPx, range, corridorCells, add) {
            var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
            var walk = function (coords, fn) {
                if (typeof coords[0] === 'number') { fn(coords); return; }
                for (var i = 0; i < coords.length; i++) { walk(coords[i], fn); }
            };
            var toCell = function (c) {
                var p = project([c[1], c[0]]);
                return [p.x / cellPx, p.y / cellPx];
            };
            walk(geometry.coordinates, function (c) {
                var q = toCell(c);
                if (q[0] < minx) { minx = q[0]; } if (q[0] > maxx) { maxx = q[0]; }
                if (q[1] < miny) { miny = q[1]; } if (q[1] > maxy) { maxy = q[1]; }
            });
            var pad = Math.ceil(corridorCells / 2) + 1;
            var x0 = Math.max(range.x0, Math.floor(minx) - pad), y0 = Math.max(range.y0, Math.floor(miny) - pad);
            var x1 = Math.min(range.x1, Math.ceil(maxx) + pad), y1 = Math.min(range.y1, Math.ceil(maxy) + pad);
            var w = x1 - x0, h = y1 - y0;
            if (w <= 0 || h <= 0) { return; }

            var c = this._raster || (this._raster = document.createElement('canvas'));
            if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
            var ctx = c.getContext('2d', { willReadFrequently: true });
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.clearRect(0, 0, w, h);
            ctx.imageSmoothingEnabled = false;
            ctx.fillStyle = '#000'; ctx.strokeStyle = '#000';
            ctx.lineCap = 'round'; ctx.lineJoin = 'round';
            ctx.lineWidth = Math.max(1, corridorCells);

            var path = function (ring, close) {
                for (var i = 0; i < ring.length; i++) {
                    var q = toCell(ring[i]);
                    if (i) { ctx.lineTo(q[0] - x0, q[1] - y0); } else { ctx.moveTo(q[0] - x0, q[1] - y0); }
                }
                if (close) { ctx.closePath(); }
            };
            var type = geometry.type, coords = geometry.coordinates;
            if (type === 'Polygon' || type === 'MultiPolygon') {
                var polys = type === 'Polygon' ? [coords] : coords;
                ctx.beginPath();
                polys.forEach(function (rings) { rings.forEach(function (ring) { path(ring, true); }); });
                ctx.fill('evenodd');
            } else if (type === 'LineString' || type === 'MultiLineString') {
                var lines = type === 'LineString' ? [coords] : coords;
                ctx.beginPath();
                lines.forEach(function (line) { path(line, false); });
                ctx.stroke();
            } else {
                return;
            }

            var data = ctx.getImageData(0, 0, w, h).data;
            var rw = range.x1 - range.x0;
            for (var py = 0; py < h; py++) {
                for (var px = 0; px < w; px++) {
                    if (data[(py * w + px) * 4 + 3] < 128) { continue; }
                    add((py + y0 - range.y0) * rw + (px + x0 - range.x0));
                }
            }
        },

        // metres per world pixel at this zoom and latitude
        _metersPerPixel: function (lat, zoom) {
            return 40075016.686 * Math.cos(lat * Math.PI / 180) / (256 * Math.pow(2, zoom));
        },

        // ── 'grid' style ────────────────────────────────────────────────
        // Cell size in metres (public_results_grid's rule unless given), then
        // in world pixels at the current zoom; cells are indexed in projected
        // world coordinates so they stay put across pans and zooms.
        _cellMeters: function () {
            if (this.options.cellMeters) { return this.options.cellMeters; }
            if (this._cellM) { return this._cellM; }
            var b = this.getBounds();
            if (!b.isValid()) { return this.options.minCellMeters; }
            var sw = L.CRS.EPSG3857.project(b.getSouthWest()), ne = L.CRS.EPSG3857.project(b.getNorthEast());
            var longer = Math.max(ne.x - sw.x, ne.y - sw.y);
            // EPSG:3857 metres are stretched by 1/cos(lat); undo for a true size.
            var lat = (b.getNorth() + b.getSouth()) / 2;
            longer *= Math.cos(lat * Math.PI / 180);
            this._cellM = Math.max(this.options.minCellMeters, longer / this.options.cellsAcross);
            return this._cellM;
        },

        _redrawGrid: function (ctx, size, ratio) {
            var map = this._map, zoom = map.getZoom();
            var b = this.getBounds();
            var lat = b.isValid() ? (b.getNorth() + b.getSouth()) / 2 : map.getCenter().lat;
            var cellM = this._cellMeters();
            var cellPx = cellM / this._metersPerPixel(lat, zoom);
            if (cellPx < 1.5) { cellPx = 1.5; }   // zoomed far out: never sub-pixel bins
            var origin = map.getPixelOrigin();
            // Only the cells in view (plus one) are counted: a city-wide polygon
            // at zoom 18 must not rasterise a million cells nobody sees.
            var tl = map.containerPointToLayerPoint([0, 0]).add(origin);
            var br = map.containerPointToLayerPoint([size.x, size.y]).add(origin);
            var range = { x0: Math.floor(tl.x / cellPx) - 1, y0: Math.floor(tl.y / cellPx) - 1,
                          x1: Math.floor(br.x / cellPx) + 2, y1: Math.floor(br.y / cellPx) + 2 };
            var corridorCells = this.options.corridorMeters / cellM;
            var bins = this._bin(function (ll) { return map.project(ll, zoom); }, cellPx, range, corridorCells);
            var hits = bins.hits, n = bins.n;
            if (!n || !hits.size) { return this; }
            var rgb = this._rgbOf(this.options.color);
            var lo = this.options.minAlpha, hi = this.options.maxAlpha;
            var rw = range.x1 - range.x0;
            ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
            hits.forEach(function (count, key) {
                var cx = (key % rw) + range.x0, cy = Math.floor(key / rw) + range.y0;
                var lp = L.point(cx * cellPx, cy * cellPx).subtract(origin);
                var cp = map.layerPointToContainerPoint(lp);
                // Snap both edges to whole pixels: neighbours share an edge exactly,
                // so translucent cells neither overlap (dark hairlines) nor gap.
                var x0 = Math.round(cp.x), y0 = Math.round(cp.y);
                var x1 = Math.round(cp.x + cellPx), y1 = Math.round(cp.y + cellPx);
                if (x0 > size.x || y0 > size.y || x1 < 0 || y1 < 0) { return; }
                var a = lo + (hi - lo) * (count / n);
                ctx.fillStyle = 'rgba(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ',' + a.toFixed(3) + ')';
                ctx.fillRect(x0, y0, Math.max(1, x1 - x0), Math.max(1, y1 - y0));
            });
            return this;
        },

        // Separable box blur over the cell field, `r` cells each side. Cheap
        // (two passes, O(cells)) and enough: the bilinear upscale smooths the rest.
        _blur: function (src, cols, rows, r) {
            if (!r) { return src; }
            var tmp = new Float32Array(src.length), out = new Float32Array(src.length);
            var w = 2 * r + 1, x, y, i, s;
            for (y = 0; y < rows; y++) {
                s = 0;
                for (x = -r; x <= r; x++) { s += x >= 0 && x < cols ? src[y * cols + x] : 0; }
                for (x = 0; x < cols; x++) {
                    tmp[y * cols + x] = s / w;
                    var add = x + r + 1, del = x - r;
                    s += (add < cols ? src[y * cols + add] : 0) - (del >= 0 ? src[y * cols + del] : 0);
                }
            }
            for (x = 0; x < cols; x++) {
                s = 0;
                for (y = -r; y <= r; y++) { s += y >= 0 && y < rows ? tmp[y * cols + x] : 0; }
                for (y = 0; y < rows; y++) {
                    out[y * cols + x] = s / w;
                    var add2 = y + r + 1, del2 = y - r;
                    s += (add2 < rows ? tmp[add2 * cols + x] : 0) - (del2 >= 0 ? tmp[del2 * cols + x] : 0);
                }
            }
            // Keep painted cells at their true share: the blur only adds a fringe.
            for (i = 0; i < src.length; i++) { if (src[i] > out[i]) { out[i] = src[i]; } }
            return out;
        },

        // 256-entry RGB lookup from a {stop: colour} gradient, like leaflet.heat's.
        _rampOf: function (gradient) {
            if (this._ramp) { return this._ramp; }
            var c = document.createElement('canvas'); c.width = 256; c.height = 1;
            var ctx = c.getContext('2d'), g = ctx.createLinearGradient(0, 0, 256, 0);
            for (var stop in gradient) { g.addColorStop(+stop, gradient[stop]); }
            ctx.fillStyle = g; ctx.fillRect(0, 0, 256, 1);
            var px = ctx.getImageData(0, 0, 256, 1).data, ramp = new Uint8ClampedArray(256 * 3);
            for (var i = 0; i < 256; i++) { ramp[i * 3] = px[i * 4]; ramp[i * 3 + 1] = px[i * 4 + 1]; ramp[i * 3 + 2] = px[i * 4 + 2]; }
            this._ramp = ramp;
            return ramp;
        },

        _rgbOf: function (hex) {
            if (this._rgb) { return this._rgb; }
            var m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
            var v = m ? parseInt(m[1], 16) : 0x4f46e5;
            this._rgb = [(v >> 16) & 255, (v >> 8) & 255, v & 255];
            return this._rgb;
        }
    });

    L.sprayAgreementLayer = function (members, options) { return new L.SprayAgreementLayer(members, options); };

    // GeoJSON LineString/Polygon/Multi* features (with properties.session_id)
    // -> shape members for a coverage surface (change responses-coverage-surface).
    L.SprayAgreementLayer.membersFromFeatures = function (features) {
        var out = [];
        var kinds = { LineString: 1, MultiLineString: 1, Polygon: 1, MultiPolygon: 1 };
        (features || []).forEach(function (f, i) {
            if (!f.geometry || !kinds[f.geometry.type]) { return; }
            out.push({ id: (f.properties && f.properties.session_id) != null ? f.properties.session_id : i,
                       geometry: f.geometry });
        });
        return out;
    };

    // GeoJSON MultiPoint features (with properties.session_id) -> clouds.
    L.SprayAgreementLayer.cloudsFromFeatures = function (features) {
        var out = [];
        (features || []).forEach(function (f, i) {
            if (!f.geometry || f.geometry.type !== 'MultiPoint') { return; }
            out.push({ id: (f.properties && f.properties.session_id) != null ? f.properties.session_id : i,
                       dots: f.geometry.coordinates.map(function (c) { return [c[1], c[0]]; }) });
        });
        return out;
    };
})();
