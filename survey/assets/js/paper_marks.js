/* The map page of a paper check (change paper-photo-entry, item 4): the printed
 * frame as a live map with the marks read off the photo, and a table that reads
 * like the printed one — a row per mark (A1, A2 …), the printed columns as
 * inputs. Rows and pins are one state: select a row and its pin lights up and
 * the photo scrolls to the mark (window.PaperReview.focusBox); drag a pin and
 * the row keeps its answers; remove a row and its pin goes. Everything is
 * serialised into the hidden input per map question in the dialect the section
 * POST already stores (feature|feature, properties = {sub: [values]}), after
 * every change, so Next / Back / the stepper need nothing special.
 * Nothing here writes markup from data: nodes are created and filled with
 * textContent. */
(function () {
    'use strict';

    function init() {
        var root = document.getElementById('paper-marks');
        var dataEl = document.getElementById('paper-map-data');
        if (!root || !dataEl || root.dataset.wired || typeof L === 'undefined') return;
        root.dataset.wired = '1';
        var data = JSON.parse(dataEl.textContent);
        var t = root.querySelector('.paper-marks__i18n').dataset;

        // zoomSnap 0: fitBounds lands on the printed frame exactly, not on the
        // next whole zoom level out.
        var map = L.map('paper-map', { zoomControl: true, attributionControl: false, zoomSnap: 0 });
        map.addLayer(basemap());
        var bounds = L.latLngBounds([data.bbox[1], data.bbox[0]], [data.bbox[3], data.bbox[2]]);
        map.fitBounds(bounds, { padding: [2, 2] });
        var fit = root.querySelector('[data-marks-fit]');
        if (fit) fit.addEventListener('click', function () { map.fitBounds(bounds, { padding: [2, 2] }); });
        var status = el('p', 'paper-marks__status');
        status.hidden = true;
        root.appendChild(status);

        var questions = data.questions.map(function (q) { return wireQuestion(q, map, root, t, status); });
        // Serialise before the form goes, whatever triggers it.
        var form = document.getElementById('section_question_form');
        var syncAll = function () { questions.forEach(function (q) { q.sync(); }); };
        if (form) form.addEventListener('submit', syncAll);
        document.body.addEventListener('htmx:configRequest', function (e) {
            if (form && (e.target === form || form.contains(e.target))) syncAll();
        });
        setTimeout(function () { map.invalidateSize(); map.fitBounds(bounds, { padding: [2, 2] }); }, 200);
    }

    // The respondent page's basemap, cloned: a Leaflet layer lives on one map only.
    function basemap() {
        var layers = window._basemapLayers || {};
        var src = null;
        Object.keys(layers).forEach(function (k) {
            if (!src || (window.map && window.map.hasLayer && window.map.hasLayer(layers[k]))) src = layers[k];
        });
        if (src && src._url) return L.tileLayer(src._url, src.options);
        return L.layerGroup();   // no basemap on this page: the pins still show over the frame's bounds
    }

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text !== undefined) n.textContent = text;
        return n;
    }
    function clear(node) {
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    function wireQuestion(q, map, root, t, status) {
        var box = root.querySelector('[data-marks-question="' + q.code + '"]');
        var tbody = box.querySelector('[data-marks-rows]');
        var input = box.querySelector('[data-marks-input]');
        var addBtn = box.querySelector('[data-marks-add]');
        var group = L.featureGroup().addTo(map);
        var rows = [];           // {label, layer, props, box, tr, inputs}
        var selected = null;
        var placing = null;

        function label(i) { return q.letter + (i + 1); }
        function renumber() {
            rows.forEach(function (r, i) {
                r.label = label(i);
                r.tr.querySelector('.lbl').textContent = r.label;
                if (r.layer && r.layer.setIcon) r.layer.setIcon(pinIcon(r.label, q.color, r === selected));
                if (r.layer && r.layer.getTooltip) { var tt = r.layer.getTooltip(); if (tt) tt.setContent(r.label); }
            });
        }
        function select(r) {
            selected = r;
            rows.forEach(function (x) {
                x.tr.classList.toggle('is-sel', x === r);
                if (x.layer && x.layer.setIcon) x.layer.setIcon(pinIcon(x.label, q.color, x === r));
            });
            if (r && r.box && window.PaperReview) window.PaperReview.focusBox(r.box);
        }
        function sync() {
            var parts = [];
            rows.forEach(function (r) {
                if (!r.layer) return;
                var geometry = geometryOf(r.layer);
                if (!geometry) return;
                var props = { question_id: q.code };
                q.subs.forEach(function (s) {
                    var v = readInput(r.inputs[s.code], s);
                    if (v.values.length) props[s.code] = v.values;
                    if (v.other) props[s.code + '_other'] = [v.other];
                });
                parts.push(JSON.stringify({ type: 'Feature', geometry: geometry, properties: props }));
            });
            input.value = parts.join('|');
        }
        function stateText(r) {
            if (!r.layer) return t.none;
            var g = geometryOf(r.layer);
            if (!g) return t.none;
            if (g.type === 'LineString') return t.line.replace('{n}', String(g.coordinates.length));
            if (g.type === 'Polygon') return t.area;
            if (g.type === 'MultiPoint') return t.cloud.replace('{n}', String(g.coordinates.length));
            return t.placed;
        }
        function refreshState(r) {
            var tag = r.tr.querySelector('.paper-marks__tag');
            tag.textContent = stateText(r);
            tag.className = 'paper-marks__tag ' + (r.layer ? 'paper-marks__tag--ok' : 'paper-marks__tag--none');
            r.tr.classList.toggle('is-empty', !r.layer);
            r.tr.classList.toggle('has-mark', !!r.layer);
            var show = r.tr.querySelector('.paper-marks__act a:not(.del)');
            if (show) show.hidden = !r.layer;
        }
        function layerFor(feature, lbl) {
            var g = feature.geometry, layer = null;
            if (g.type === 'Point') {
                layer = L.marker([g.coordinates[1], g.coordinates[0]], { draggable: true, icon: pinIcon(lbl, q.color, false) });
            } else if (g.type === 'LineString') {
                layer = L.polyline(g.coordinates.map(function (c) { return [c[1], c[0]]; }), { color: q.color });
            } else if (g.type === 'Polygon') {
                layer = L.polygon(g.coordinates[0].map(function (c) { return [c[1], c[0]]; }), { color: q.color });
            } else if (g.type === 'MultiPoint') {
                var dots = g.coordinates.map(function (c) { return [c[1], c[0]]; });
                layer = L.sprayLayer ? L.sprayLayer(dots, { color: q.color })
                    : L.featureGroup(dots.map(function (d) { return L.circleMarker(d, { radius: 2, color: q.color }); }));
                layer._cloud = g.coordinates;
            }
            if (layer && g.type !== 'Point' && g.type !== 'MultiPoint') {
                layer.bindTooltip(lbl, { permanent: true, direction: 'center', className: 'paper-marks__tip' });
                if (layer.editing) layer.editing.enable();
            }
            return layer;
        }
        function attach(r) {
            if (!r.layer) return;
            group.addLayer(r.layer);
            r.layer.on('click', function () { select(r); });
            r.layer.on('dragend edit', function () { sync(); refreshState(r); });
            r.layer.on('drag', sync);
        }
        function removeRow(r) {
            if (r.layer) group.removeLayer(r.layer);
            r.layer = null;
            var i = rows.indexOf(r);
            if (i >= q.rows && i === rows.length - 1) {
                // A row beyond the printed ones goes away; a printed row stays, empty.
                rows.splice(i, 1);
                r.tr.parentNode.removeChild(r.tr);
                renumber();
            } else {
                refreshState(r);
                emptyCell(r);
            }
            if (selected === r) select(null);
            sync();
        }
        function emptyCell(r) {
            // A row with no mark: the printed columns give way to one line with "place it on the map".
            var cells = r.tr.querySelectorAll('td.sub');
            cells.forEach(function (c, i) { c.hidden = i > 0; });
            var first = cells[0];
            if (!first) return;
            first.colSpan = cells.length;
            clear(first);
            first.appendChild(el('span', 'empty', t.empty + ' '));
            var a = el('a', '', t.place);
            a.href = '#';
            a.addEventListener('click', function (e) { e.preventDefault(); startPlacing(r); });
            first.appendChild(a);
        }
        function fillCells(r) {
            var cells = r.tr.querySelectorAll('td.sub');
            cells.forEach(function (c, i) {
                c.hidden = false;
                c.colSpan = 1;
                clear(c);
                c.appendChild(r.inputs[q.subs[i].code]);
            });
        }
        function buildRow(i, feature, markBox) {
            var r = { label: label(i), layer: null, props: (feature && feature.properties) || {}, box: markBox || null, inputs: {} };
            var tr = el('tr');
            tr.appendChild(el('td', 'lbl', r.label));
            var st = el('td');
            st.appendChild(el('span', 'paper-marks__tag', ''));
            tr.appendChild(st);
            q.subs.forEach(function (s) {
                r.inputs[s.code] = makeInput(s, r.props[s.code], r.props[s.code + '_other']);
                r.inputs[s.code].addEventListener('change', sync);
                r.inputs[s.code].addEventListener('input', sync);
                r.inputs[s.code].addEventListener('focusin', function () { select(r); });
                tr.appendChild(el('td', 'sub'));
            });
            var act = el('td', 'paper-marks__act');
            var show = el('a', '', t.show);
            show.href = '#';
            show.addEventListener('click', function (e) {
                e.preventDefault();
                select(r);
                if (r.layer) { var ll = centre(r.layer); if (ll) map.panTo(ll); }
            });
            var del = el('a', 'del', '✕');
            del.href = '#';
            del.title = t.remove;
            del.addEventListener('click', function (e) { e.preventDefault(); removeRow(r); });
            act.appendChild(show);
            act.appendChild(del);
            tr.appendChild(act);
            tr.addEventListener('click', function (e) { if (e.target.tagName !== 'A') select(r); });
            r.tr = tr;
            tbody.appendChild(tr);
            if (feature) {
                r.layer = layerFor(feature, r.label);
                attach(r);
                fillCells(r);
            } else {
                emptyCell(r);
            }
            refreshState(r);
            return r;
        }
        function startPlacing(r) {
            if (placing) stopPlacing();
            placing = r;
            root.classList.add('paper-marks__placing');
            status.hidden = false;
            if (q.type === 'point') {
                status.textContent = t.click;
                map.once('click', function (e) {
                    finishPlacing({ type: 'Feature', geometry: { type: 'Point', coordinates: [e.latlng.lng, e.latlng.lat] }, properties: {} });
                });
            } else {
                status.textContent = t.draw;
                var handler = q.type === 'line' ? new L.Draw.Polyline(map, { shapeOptions: { color: q.color } })
                    : new L.Draw.Polygon(map, { shapeOptions: { color: q.color } });
                handler.enable();
                map.once(L.Draw.Event.CREATED, function (e) {
                    var gj = e.layer.toGeoJSON();
                    if (q.type === 'spraycan') gj.geometry = { type: 'MultiPoint', coordinates: gj.geometry.coordinates[0] };
                    finishPlacing(gj);
                });
            }
        }
        function finishPlacing(feature) {
            var r = placing;
            stopPlacing();
            if (!r) return;
            r.layer = layerFor(feature, r.label);
            attach(r);
            fillCells(r);
            refreshState(r);
            select(r);
            sync();
        }
        function stopPlacing() {
            placing = null;
            root.classList.remove('paper-marks__placing');
            status.hidden = true;
        }

        var features = q.features || [];
        var n = Math.max(q.rows || 0, features.length);
        for (var i = 0; i < n; i++) {
            rows.push(buildRow(i, features[i] || null, (q.boxes || [])[i]));
        }
        addBtn.addEventListener('click', function () {
            if (q.max && rows.filter(function (r) { return r.layer; }).length >= q.max) return;
            var r = buildRow(rows.length, null, null);
            rows.push(r);
            startPlacing(r);
        });
        sync();
        return { sync: sync };
    }

    function pinIcon(lbl, color, sel) {
        var wrap = el('div', 'paper-pin__wrap');
        wrap.style.setProperty('--pin', color || '#2563eb');
        wrap.appendChild(el('span', 'paper-pin__label', lbl));
        wrap.appendChild(el('span', 'paper-pin__dot'));
        // Serialised from nodes built above with textContent — Leaflet's divIcon
        // takes a string; nothing from the data reaches it unescaped.
        return L.divIcon({ className: 'paper-pin' + (sel ? ' is-sel' : ''), html: wrap.outerHTML, iconSize: [0, 0] });
    }
    function centre(layer) {
        if (layer.getLatLng) return layer.getLatLng();
        if (layer.getBounds) { var b = layer.getBounds(); return b.isValid && b.isValid() ? b.getCenter() : null; }
        return null;
    }
    function geometryOf(layer) {
        if (layer._cloud) return { type: 'MultiPoint', coordinates: layer._cloud };
        if (layer.getLatLng) { var p = layer.getLatLng(); return { type: 'Point', coordinates: [p.lng, p.lat] }; }
        if (layer.toGeoJSON) {
            var gj = layer.toGeoJSON();
            return gj.geometry || (gj.features && gj.features[0] && gj.features[0].geometry) || null;
        }
        return null;
    }

    // Inputs in the printed columns' shapes: one select for a choice, checkboxes
    // for a multichoice, text/number/date for the rest. Values are option CODES.
    function makeInput(s, values, other) {
        values = values || [];
        var wrap;
        if (s.type === 'choice' || s.type === 'rating' || s.type === 'thumbs') {
            wrap = el('select');
            var none = el('option', '', '—');
            none.value = '';
            wrap.appendChild(none);
            (s.options || []).forEach(function (o) {
                var opt = el('option', '', o.label);
                opt.value = o.code;
                if (values.indexOf(o.code) >= 0) opt.selected = true;
                wrap.appendChild(opt);
            });
        } else if (s.type === 'multichoice') {
            wrap = el('div', 'chks');
            (s.options || []).forEach(function (o) {
                var lab = el('label', 'chk');
                var cb = el('input');
                cb.type = 'checkbox';
                cb.value = o.code;
                cb.checked = values.indexOf(o.code) >= 0;
                lab.appendChild(cb);
                lab.appendChild(document.createTextNode(o.label));
                wrap.appendChild(lab);
            });
        } else {
            wrap = el('input');
            wrap.type = s.type === 'number' || s.type === 'range' ? 'number' : (s.type === 'datetime' ? 'datetime-local' : 'text');
            wrap.value = values.length ? String(values[0]) : '';
        }
        if (other && other.length && wrap.tagName === 'SELECT') wrap.dataset.other = other[0];
        return wrap;
    }
    function readInput(node, s) {
        if (!node) return { values: [], other: '' };
        if (node.tagName === 'SELECT') return { values: node.value ? [node.value] : [], other: node.dataset.other || '' };
        if (node.classList.contains('chks')) {
            return { values: Array.prototype.map.call(node.querySelectorAll('input:checked'), function (c) { return c.value; }), other: '' };
        }
        var v = (node.value || '').trim();
        return { values: v ? [v] : [], other: '' };
    }

    document.addEventListener('DOMContentLoaded', init);
    document.body.addEventListener('htmx:afterSettle', function () { setTimeout(init, 0); });
    if (document.readyState !== 'loading') setTimeout(init, 0);
})();
