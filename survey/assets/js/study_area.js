/* The study area on the respondent map (change map-layers-study-area, spec survey-study-area).
 *
 * window.StudyArea.show(map, meta) — meta from the section's #section-data[data-study-area]: {url,
 * fog, refuse_outside, message, bounds}, or null when the section uses no area (change
 * section-study-area: a section uses the survey's area, its own, or none). The outline is fetched
 * from the gated endpoint (never inlined), drawn under the answers with a grey fog outside when the
 * creator kept fog on; a different area on the next section replaces it, null removes it. show()
 * answers whether the area changed, and the page then opens the map on it unless the section's own
 * start lies inside (openOn).
 *
 * StudyArea.admit(layer, type) is asked from the draw:created handler, like BudgetQuestion.admit:
 * with the rule on, a point outside, or a line/area with a corner more than 5 m outside, is not
 * placed and the creator's message shows; a spray cloud keeps only its dots inside. The section
 * POST checks again on the server (survey/study_area_guard.py).
 */
(function () {
    var TOLERANCE_M = 5;
    var state = {map: null, meta: null, rings: [], bounds: null, toast: null, timer: null, layers: [], token: 0};

    function ringsOf(geometry) {
        var polys = geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];
        return polys.map(function (p) { return p[0]; });   // exterior rings, [lng, lat]
    }
    function inRing(lng, lat, ring) {
        var inside = false;
        for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
            if (((yi > lat) !== (yj > lat)) && (lng < (xj - xi) * (lat - yi) / ((yj - yi) || 1e-12) + xi)) inside = !inside;
        }
        return inside;
    }
    function metresToRing(lng, lat, ring) {
        var k = Math.cos(lat * Math.PI / 180), best = Infinity;
        for (var i = 0; i < ring.length - 1; i++) {
            var ax = (ring[i][0] - lng) * k, ay = ring[i][1] - lat;
            var bx = (ring[i + 1][0] - lng) * k, by = ring[i + 1][1] - lat;
            var dx = bx - ax, dy = by - ay, len = dx * dx + dy * dy;
            var t = len ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len)) : 0;
            var px = ax + t * dx, py = ay + t * dy;
            best = Math.min(best, Math.sqrt(px * px + py * py) * 111320);
        }
        return best;
    }
    function contains(latlng, tolerance) {
        if (!state.rings.length) return true;
        for (var i = 0; i < state.rings.length; i++) {
            if (inRing(latlng.lng, latlng.lat, state.rings[i])) return true;
        }
        if (!tolerance) return false;
        for (var j = 0; j < state.rings.length; j++) {
            if (metresToRing(latlng.lng, latlng.lat, state.rings[j]) <= tolerance) return true;
        }
        return false;
    }
    function flatten(latlngs, out) {
        out = out || [];
        (latlngs || []).forEach(function (ll) { if (Array.isArray(ll)) flatten(ll, out); else out.push(ll); });
        return out;
    }
    function say() {
        if (!state.map || !state.meta || !state.meta.message) return;
        var box = state.toast;
        if (!box) {
            box = state.toast = document.createElement('div');
            box.className = 'study-area-toast';
            box.setAttribute('role', 'status');
            state.map.getContainer().appendChild(box);
        }
        box.textContent = state.meta.message;
        box.hidden = false;
        clearTimeout(state.timer);
        state.timer = setTimeout(function () { box.hidden = true; }, 4000);
    }

    function ensurePane(map) {
        if (map.getPane('studyAreaPane')) return;
        map.createPane('studyAreaPane');
        map.getPane('studyAreaPane').style.zIndex = 345;   // above tiles, below reference layers (350)
        map.getPane('studyAreaPane').style.pointerEvents = 'none';
    }
    function removeDrawn() {
        state.layers.forEach(function (layer) { if (state.map) state.map.removeLayer(layer); });
        state.layers = [];
        state.rings = [];
    }
    function draw(geometry) {
        var map = state.map;
        removeDrawn();
        ensurePane(map);
        state.rings = ringsOf(geometry);
        if (state.meta.fog) {
            var world = [[-89.9, -539.9], [-89.9, 539.9], [89.9, 539.9], [89.9, -539.9]];
            var holes = state.rings.map(function (r) { return r.map(function (c) { return [c[1], c[0]]; }); });
            state.layers.push(L.polygon([world].concat(holes), {pane: 'studyAreaPane', stroke: false,
                fillColor: '#1f2937', fillOpacity: 0.35, interactive: false}).addTo(map));
        }
        state.layers.push(L.geoJSON(geometry, {pane: 'studyAreaPane', interactive: false,
            style: {color: '#4f46e5', weight: 2, fill: false, opacity: 0.9}}).addTo(map));
    }

    window.StudyArea = {
        active: false,
        // Show a section's area (null = none). Returns whether the area changed.
        show: function (map, meta) {
            if (!map) return false;
            var url = meta && meta.url ? meta.url : null;
            var current = state.meta && state.meta.url ? state.meta.url : null;
            if (url === current && state.map === map) return false;
            state.map = map;
            state.token += 1;
            removeDrawn();
            if (state.toast) state.toast.hidden = true;
            if (!url) {
                state.meta = null;
                state.bounds = null;
                this.active = false;
                return current !== null;
            }
            state.meta = meta;
            this.active = true;
            state.bounds = meta.bounds ? L.latLngBounds([meta.bounds[1], meta.bounds[0]], [meta.bounds[3], meta.bounds[2]]) : null;
            var token = state.token;
            fetch(url, {credentials: 'same-origin'}).then(function (r) {
                if (!r.ok) throw new Error('study area HTTP ' + r.status);
                return r.json();
            }).then(function (fc) {
                if (token !== state.token) return;   // the respondent has moved on to another area
                var f = (fc.features || [])[0];
                if (f) draw(f.geometry);
            }).catch(function (err) { console.warn('Study area failed:', err); });
            return true;
        },
        init: function (map, meta) { return this.show(map, meta); },
        // The map opens on the area unless the section's own start lies inside it.
        openOn: function (lat, lng) {
            if (!state.bounds || !state.map) return false;
            if (isFinite(lat) && isFinite(lng) && state.bounds.contains([lat, lng])) return false;
            try { state.map.fitBounds(state.bounds, {padding: [20, 20], animate: false}); } catch (e) { return false; }
            return true;
        },
        admit: function (layer, type) {
            if (!state.meta || !state.meta.refuse_outside || !state.rings.length) return true;
            if (type === 'spray' && layer.getDots) {
                var dots = layer.getDots();
                var kept = dots.filter(function (ll) { return contains(ll, 0); });
                if (kept.length !== dots.length) { layer.setDots(kept); say(); }
                return kept.length > 0;
            }
            var points = layer.getLatLng ? [layer.getLatLng()] : flatten(layer.getLatLngs ? layer.getLatLngs() : []);
            var tolerance = layer.getLatLng ? 0 : TOLERANCE_M;
            var ok = points.every(function (ll) { return contains(ll, tolerance); });
            if (!ok) say();
            return ok;
        },
        contains: function (latlng) { return contains(latlng, 0); }
    };
})();
