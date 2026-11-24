/*
 * The Wizard's study area on the create page (change map-layers-study-area, D8b; spec
 * ai-survey-generation "The Wizard sets the study area").
 *
 * WizardStudyArea.init(map, {url, isTouched}) — once, after the create map exists.
 * WizardStudyArea.propose(query) — the map was aimed at a place (brief prefill or a search
 * result): look up its boundary and show it with the respondent's fog, unless the creator removed
 * the area or edited the outline — then only offer "Use the boundary of …".
 *
 * Handles: Edit outline (Leaflet.draw vertex editing), corridor width for a street, answers
 * outside allowed / not allowed, Remove. The hidden fields carry what the creator kept:
 * study_area_mode auto | set | off. Text goes in with textContent only.
 */
(function () {
    'use strict';
    var STYLE = {color: '#4f46e5', weight: 2, fillOpacity: 0.04};
    var FOG = {stroke: false, fillColor: '#1f2937', fillOpacity: 0.3, interactive: false};
    var WORLD = [[-89.9, -539.9], [-89.9, 539.9], [89.9, 539.9], [89.9, -539.9]];

    var S = {}, map = null, opts = {}, group = null, fog = null, editor = null, seq = 0;
    var state = {mode: 'auto', found: null, edited: false, offer: null};
    var $ = function (id) { return document.getElementById(id); };

    function fmt(text, values) {
        return String(text || '').replace(/%\((\w+)\)s/g, function (_m, k) { return values[k] == null ? '' : values[k]; });
    }
    function setField(id, value) { var el = $(id); if (el) el.value = value == null ? '' : value; }

    function currentGeometry() {
        var polys = [];
        group.eachLayer(function (layer) {
            var g = layer.toGeoJSON().geometry;
            if (g.type === 'Polygon') polys.push(g.coordinates);
            else if (g.type === 'MultiPolygon') polys = polys.concat(g.coordinates);
        });
        return {type: 'MultiPolygon', coordinates: polys};
    }
    function drawFog() {
        if (fog) { map.removeLayer(fog); fog = null; }
        var holes = [];
        group.eachLayer(function (layer) {
            var rings = layer.getLatLngs();
            holes.push(Array.isArray(rings[0]) ? rings[0] : rings);
        });
        if (holes.length) fog = L.polygon([WORLD].concat(holes), Object.assign({pane: 'wsaFog'}, FOG)).addTo(map);
    }
    // A city boundary has thousands of vertices; nobody can drag those. Before editing, the outline
    // is simplified on screen (Douglas–Peucker in pixels at the current zoom) to about MAX_HANDLES
    // corners — the shape stays, the coastline detail goes, which is what "move the edge" needs.
    var MAX_HANDLES = 60;
    var MIN_PART_PX = 15;   // parts smaller than this on screen (enclaves, islets) are dropped
    function countVertices() {
        var n = 0;
        group.eachLayer(function (layer) { layer.getLatLngs().forEach(function (ring) { n += ring.length; }); });
        return n;
    }
    function simplifyForEditing() {
        if (countVertices() <= MAX_HANDLES) return false;
        var originals = [];
        group.eachLayer(function (layer) {
            var b = layer.getBounds();
            var size = map.latLngToLayerPoint(b.getNorthEast()).subtract(map.latLngToLayerPoint(b.getSouthWest()));
            if (Math.max(Math.abs(size.x), Math.abs(size.y)) < MIN_PART_PX && group.getLayers().length > 1) {
                group.removeLayer(layer);
                return;
            }
            originals.push([layer, layer.getLatLngs()]);
        });
        for (var tolerance = 2; tolerance < 4096; tolerance *= 1.5) {
            var total = 0;
            originals.forEach(function (pair) {
                var rings = pair[1].map(function (ring) {
                    var pts = ring.map(function (ll) { return map.latLngToLayerPoint(ll); });
                    var kept = L.LineUtil.simplify(pts, tolerance);
                    if (kept.length < 3) kept = pts.length > 3 ? [pts[0], pts[Math.floor(pts.length / 3)], pts[Math.floor(2 * pts.length / 3)]] : pts;
                    total += kept.length;
                    return kept.map(function (p) { return map.layerPointToLatLng(p); });
                });
                pair[2] = rings;
            });
            if (total <= MAX_HANDLES) break;
        }
        // New layers, not setLatLngs: Leaflet.draw keeps the vertex handlers of the layer it met.
        originals.forEach(function (pair) {
            group.removeLayer(pair[0]);
            L.polygon(pair[2], STYLE).addTo(group);
        });
        return true;
    }
    function stopEditing() {
        if (editor) { editor.disable(); editor = null; }
        $('wsa-edit').textContent = S.edit;
        $('wsa-edit').setAttribute('aria-pressed', 'false');
    }
    function clearArea() {
        stopEditing();
        group.clearLayers();
        if (fog) { map.removeLayer(fog); fog = null; }
    }
    function syncFields() {
        var set = state.mode === 'set' && group.getLayers().length;
        setField('wsa-mode', set ? 'set' : state.mode === 'off' ? 'off' : 'auto');
        setField('wsa-geometry', set ? JSON.stringify(currentGeometry()) : '');
        setField('wsa-place', set && state.found ? state.found.name : '');
        setField('wsa-osm-ref', set && state.found ? state.found.osm_ref : '');
    }

    function show(view) {
        var box = $('wsa');
        box.hidden = false;
        box.classList.toggle('off', view !== 'area');
        $('wsa-actions').hidden = view !== 'area';
        $('wsa-rule').hidden = view !== 'area';
        $('wsa-widths').hidden = !(view === 'area' && state.found && state.found.kind === 'line');
        $('wsa-use').hidden = !state.offer || view === 'area' || view === 'looking';
        if (state.offer) $('wsa-use').textContent = fmt(S.use, {place: state.offer});
        // The map shrinks to keep the strip on the screen (the page fits one screen).
        var right = box.closest('.create-right');
        if (right) {
            var full = view === 'area';
            if (right.classList.contains('has-wsa') !== full || right.classList.contains('has-wsa-msg') === full) {
                right.classList.toggle('has-wsa', full);
                right.classList.toggle('has-wsa-msg', !full);
                setTimeout(function () { map.invalidateSize(); }, 50);
            }
        }
    }
    function say(name, sub) { $('wsa-name').textContent = name ? '· ' + name : ''; $('wsa-sub').textContent = sub || ''; }
    function areaSub() {
        var km2 = state.found ? Number(state.found.km2 || 0).toLocaleString() : '';
        return fmt(state.edited ? S.edited : S.sub, {km2: km2});
    }

    function setArea(found) {
        clearArea();
        state.found = found;
        state.mode = 'set';
        state.edited = false;
        state.offer = null;
        var parts = found.geometry.type === 'MultiPolygon' ? found.geometry.coordinates : [found.geometry.coordinates];
        parts.forEach(function (rings) {
            L.polygon(rings.map(function (ring) { return ring.map(function (c) { return [c[1], c[0]]; }); }),
                STYLE).addTo(group);
        });
        drawFog();
        // Respondents open on the area: frame it while the creator has not framed the map.
        if (!opts.isTouched() && group.getLayers().length) map.fitBounds(group.getBounds(), {padding: [20, 20]});
        document.querySelectorAll('#wsa-widths [data-width]').forEach(function (b) {
            b.classList.toggle('active', Number(b.getAttribute('data-width')) === Number(found.width));
        });
        say(found.name, areaSub());
        show('area');
        syncFields();
    }

    function fetchBoundary(params, label) {
        var mine = ++seq;
        var keepOffer = state.offer;
        say('', fmt(S.looking, {place: label}));
        show('looking');
        var url = opts.url + '?' + new URLSearchParams(params).toString();
        return fetch(url, {credentials: 'same-origin'}).then(function (r) { return r.json(); }).then(function (d) {
            if (mine !== seq) return;
            if (d && d.found) { setArea(d); return; }
            clearArea();
            state.mode = 'auto';
            state.found = null;
            state.offer = keepOffer;
            say('', d && d.unavailable ? S.down : fmt(S.none, {place: label}));
            show('message');
            syncFields();
        }).catch(function () {
            if (mine !== seq) return;
            say('', S.down);
            show('message');
        });
    }

    window.WizardStudyArea = {
        init: function (theMap, options) {
            map = theMap;
            opts = options || {};
            opts.isTouched = opts.isTouched || function () { return false; };
            try { S = JSON.parse(($('wsa-strings') || {}).textContent || '{}'); } catch (e) { S = {}; }
            map.createPane('wsaFog');
            map.getPane('wsaFog').style.zIndex = 345;
            map.getPane('wsaFog').style.pointerEvents = 'none';
            group = L.featureGroup().addTo(map);
            if (L.drawLocal) L.drawLocal.edit.handlers.edit.tooltip.text = S.editHint || '';
            if (L.drawLocal) L.drawLocal.edit.handlers.edit.tooltip.subtext = '';

            $('wsa-edit').addEventListener('click', function () {
                if (editor) { stopEditing(); say(state.found && state.found.name, areaSub()); return; }
                if (!L.EditToolbar || !group.getLayers().length) return;
                if (simplifyForEditing()) {
                    state.edited = true;
                    drawFog();
                    syncFields();
                }
                editor = new L.EditToolbar.Edit(map, {featureGroup: group});
                editor.enable();
                $('wsa-edit').textContent = S.done;
                $('wsa-edit').setAttribute('aria-pressed', 'true');
                $('wsa-sub').textContent = S.editing;
            });
            map.on('draw:editvertex draw:editmove', function () {
                state.edited = true;
                drawFog();
                syncFields();
            });
            $('wsa-remove').addEventListener('click', function () {
                seq++;
                clearArea();
                state.offer = state.found ? state.found.name : state.offer;
                state.mode = 'off';
                say('', S.removed);
                show('message');
                syncFields();
            });
            $('wsa-use').addEventListener('click', function () {
                if (!state.offer) return;
                var label = state.offer;
                state.edited = false;
                state.mode = 'auto';
                fetchBoundary({q: label}, label);
            });
            document.querySelectorAll('#wsa-widths [data-width]').forEach(function (b) {
                b.addEventListener('click', function () {
                    if (!state.found) return;
                    fetchBoundary({osm_ref: state.found.osm_ref, width: b.getAttribute('data-width')}, state.found.name);
                });
            });
            document.querySelectorAll('input[name="wsa_refuse_choice"]').forEach(function (r) {
                r.addEventListener('change', function () { setField('wsa-refuse', r.checked && r.value === '1' ? '1' : ''); });
            });
        },

        propose: function (query) {
            if (!map || !query) return;
            if (state.mode === 'off' || state.edited) {
                // The creator removed or shaped the area: never overwrite it, only offer.
                state.offer = query;
                show(state.mode === 'off' ? 'message' : 'area');
                $('wsa-use').hidden = false;
                $('wsa-use').textContent = fmt(S.use, {place: query});
                return;
            }
            fetchBoundary({q: query}, query);
        }
    };
})();
