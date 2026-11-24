/* The study area editor (change map-layers-study-area, spec survey-study-area).
 *
 * Find a place by name (OpenStreetMap through the server), pick a candidate — a boundary as it
 * is, a street as a corridor of a picked width, a point as a rectangle — then move, add or remove
 * corners and Save. Upload, a layer of the survey and drawing are the other ways in. Nothing is
 * stored until Save; the rules (fog, answers outside, message) save at once once an area exists.
 * Expects `map` (Leaflet) from the page and Leaflet.draw. Text from the server is set with
 * textContent only. With `data-section` the page edits that map section's own area (change
 * section-study-area): every POST names the section, the outline may start from the survey's
 * (unsaved), and "Use the survey's area" returns the section to it.
 */
(function () {
    var root = document.getElementById('sae');
    if (!root || typeof map === 'undefined') return;
    var urls = JSON.parse(root.dataset.urls);
    var S = JSON.parse(root.dataset.strings);
    var csrf = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
    var statusEl = document.getElementById('sae-status');
    var errorEl = document.getElementById('sae-error');
    var saveBtn = document.getElementById('sae-save');
    var hint = document.getElementById('sae-hint');
    var area = JSON.parse(document.getElementById('sae-area').textContent || 'null');
    var startEl = document.getElementById('sae-start-area');
    var startArea = startEl ? JSON.parse(startEl.textContent || 'null') : null;
    var sectionId = root.dataset.section || '';

    var group = new L.FeatureGroup().addTo(map);
    var editor = null;
    var source = area ? area.source : 'draw';
    var placeName = area ? area.place_name : '';
    var osmRef = area ? area.osm_ref : '';
    var STYLE = {color: '#4f46e5', weight: 3, fillOpacity: 0.08};

    function setStatus(text) { statusEl.textContent = text || ''; }
    function setError(text) { errorEl.textContent = text || ''; }
    function showHint(text) { hint.textContent = text || ''; hint.hidden = !text; }
    function asJson(r) {
        if (r.status === 204) return null;
        return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || 'Request failed'); return d; });
    }
    function post(url, body) {
        if (sectionId && body && body.append) body.append('section', sectionId);
        return fetch(url, {method: 'POST', headers: {'X-CSRFToken': csrf}, body: body}).then(asJson);
    }
    function get(url) { return fetch(url, {headers: {'X-CSRFToken': csrf}}).then(asJson); }
    function dirty() { saveBtn.disabled = !group.getLayers().length; setStatus(group.getLayers().length ? S.unsaved : ''); }

    function stopEditing() { if (editor) { editor.disable(); editor = null; } }
    // Leaflet.draw shows its own tooltip by the cursor: say ours there instead of a second hint.
    if (L.drawLocal) {
        L.drawLocal.edit.handlers.edit.tooltip.text = S.editHint;
        L.drawLocal.edit.handlers.edit.tooltip.subtext = '';
        L.drawLocal.draw.handlers.polygon.tooltip.start = S.drawHint;
    }
    function startEditing() {
        stopEditing();
        if (!group.getLayers().length || !L.EditToolbar) return;
        editor = new L.EditToolbar.Edit(map, {featureGroup: group});
        editor.enable();
        showHint('');
    }
    function setGeometry(geometry, fit) {
        stopEditing();
        group.clearLayers();
        // One editable L.Polygon per part: Leaflet.draw edits polygons, not multipolygons.
        var parts = geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];
        parts.forEach(function (rings) {
            L.polygon(rings.map(function (ring) { return ring.map(function (c) { return [c[1], c[0]]; }); }), STYLE).addTo(group);
        });
        if (fit !== false && group.getLayers().length) map.fitBounds(group.getBounds(), {padding: [30, 30]});
        startEditing();
        dirty();
    }
    function currentGeometry() {
        var polys = [];
        group.eachLayer(function (layer) {
            var g = layer.toGeoJSON().geometry;
            if (g.type === 'Polygon') polys.push(g.coordinates);
            else if (g.type === 'MultiPolygon') polys = polys.concat(g.coordinates);
        });
        return {type: 'MultiPolygon', coordinates: polys};
    }
    map.on('draw:editvertex draw:editmove draw:editresize', dirty);

    if (area && area.geometry) { setGeometry(area.geometry); setStatus(''); saveBtn.disabled = true; }
    else if (startArea && startArea.geometry) {
        // A section's own area starts from the survey's outline; nothing is stored until Save.
        source = startArea.source; placeName = startArea.place_name || ''; osmRef = startArea.osm_ref || '';
        setGeometry(startArea.geometry);
    }

    // ── Find the place ────────────────────────────────────────────────────
    var cands = document.getElementById('sae-cands');
    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text != null) node.textContent = text;
        return node;
    }
    function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
    function pick(item, width, li) {
        setError('');
        get(urls.candidate + '?osm_ref=' + encodeURIComponent(item.osm_ref) + (width ? '&width=' + width : ''))
            .then(function (found) {
                cands.querySelectorAll('.sae-cand').forEach(function (node) { node.classList.toggle('sel', node === li); });
                source = 'place'; placeName = item.name.slice(0, 255); osmRef = item.osm_ref;
                setGeometry(found.geometry);
            }).catch(function (e) { setError(e.message); });
    }
    function widthButtons(item, li) {
        var box = el('div', 'sae-widths');
        [50, 100, 200].forEach(function (w) {
            var b = el('button', 'btn btn-sm ' + (w === 100 ? 'btn-primary' : 'btn-outline-secondary'), w + ' m');
            b.type = 'button';
            b.addEventListener('click', function (ev) {
                ev.stopPropagation();
                box.querySelectorAll('button').forEach(function (x) { x.className = 'btn btn-sm btn-outline-secondary'; });
                b.className = 'btn btn-sm btn-primary';
                pick(item, w, li);
            });
            box.appendChild(b);
        });
        return box;
    }
    function render(list) {
        clear(cands);
        if (!list.length) { cands.appendChild(el('li', 'pr-help', S.none)); return; }
        list.forEach(function (item) {
            var li = el('li', 'sae-cand');
            li.tabIndex = 0;
            var note = item.kind === 'point' ? S.noBoundary
                : (item.kind === 'line' ? S.corridor + (item.short_segment ? ' · ' + S.segment : '') : item.type);
            li.appendChild(el('b', '', item.name));
            li.appendChild(el('small', '', note));
            if (item.kind === 'line') li.appendChild(widthButtons(item, li));
            var choose = function () { pick(item, item.kind === 'line' ? 100 : null, li); };
            li.addEventListener('click', choose);
            li.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') choose(); });
            cands.appendChild(li);
        });
    }
    document.getElementById('sae-search').addEventListener('submit', function (ev) {
        ev.preventDefault();
        var q = document.getElementById('sae-q').value.trim();
        if (!q) return;
        setError('');
        setStatus('…');
        get(urls.lookup + '?q=' + encodeURIComponent(q))
            .then(function (d) { setStatus(''); render(d.candidates || []); })
            .catch(function (e) { setStatus(''); clear(cands); setError(e.message); });
    });

    // ── Other ways in ─────────────────────────────────────────────────────
    var file = document.getElementById('sae-file');
    file.addEventListener('change', function () {
        var chosen = file.files[0];
        if (!chosen) return;
        var fd = new FormData();
        fd.append('file', chosen);
        setError('');
        post(urls.upload, fd).then(function (d) {
            source = 'upload'; placeName = chosen.name.replace(/\.[^.]+$/, ''); osmRef = '';
            setGeometry(d.geometry);
        }).catch(function (e) { setError(e.message); }).then(function () { file.value = ''; });
    });
    var useBtn = document.getElementById('sae-layer-use');
    if (useBtn) useBtn.addEventListener('click', function () {
        var sel = document.getElementById('sae-layer');
        if (!sel.value) return;
        var fd = new FormData();
        fd.append('layer', sel.value);
        fd.append('remove_layer', '0');
        setError('');
        post(urls.fromLayer, fd).then(function () { window.location.reload(); }).catch(function (e) { setError(e.message); });
    });
    document.getElementById('sae-draw').addEventListener('click', function () {
        stopEditing();
        group.clearLayers();
        dirty();
        showHint('');
        new L.Draw.Polygon(map, {shapeOptions: STYLE, allowIntersection: false}).enable();
    });
    map.on(L.Draw.Event.CREATED, function (ev) {
        group.addLayer(ev.layer.setStyle(STYLE));
        source = 'draw'; placeName = ''; osmRef = '';
        startEditing();
        dirty();
    });

    // ── Save, rules, remove ──────────────────────────────────────────────
    saveBtn.addEventListener('click', function () {
        if (!group.getLayers().length) return;
        var fd = new FormData();
        fd.append('geometry', JSON.stringify(currentGeometry()));
        fd.append('source', source);
        fd.append('place_name', placeName || '');
        fd.append('osm_ref', osmRef || '');
        setError('');
        setStatus(S.saving);
        post(urls.save, fd).then(function (d) {
            area = d.area;
            setGeometry(area.geometry, false);
            saveBtn.disabled = true;
            setStatus(S.saved);
            document.getElementById('sae-rules').hidden = false;
            // A new area (a section's starts with the survey's rules): show the rules it saved with.
            document.getElementById('sae-fog').checked = !!area.fog;
            document.querySelectorAll('input[name="sae_refuse"]').forEach(function (r) {
                r.checked = r.value === (area.refuse_outside ? '1' : '0');
            });
            document.getElementById('sae-msg-box').hidden = !area.refuse_outside;
            document.getElementById('sae-summary').textContent =
                (area.place_name ? area.place_name + ' · ' : '') + area.area_km2 + ' km²';
        }).catch(function (e) { setStatus(''); setError(e.message); });
    });
    function saveSettings(fd) {
        setError('');
        post(urls.settings, fd).then(function () { setStatus(S.saved); }).catch(function (e) { setError(e.message); });
    }
    document.getElementById('sae-fog').addEventListener('change', function (ev) {
        var fd = new FormData(); fd.append('fog', ev.target.checked ? '1' : '0'); saveSettings(fd);
    });
    document.querySelectorAll('input[name="sae_refuse"]').forEach(function (radio) {
        radio.addEventListener('change', function () {
            document.getElementById('sae-msg-box').hidden = radio.value !== '1';
            var fd = new FormData(); fd.append('refuse_outside', radio.value); saveSettings(fd);
        });
    });
    document.getElementById('sae-msg').addEventListener('change', function (ev) {
        var fd = new FormData(); fd.append('message', ev.target.value); saveSettings(fd);
    });
    var removeBtn = document.getElementById('sae-remove');
    if (removeBtn) removeBtn.addEventListener('click', function () {
        var go = function () {
            post(urls.clear, new FormData()).then(function () {
                if (sectionId) window.location = urls.back; else window.location.reload();
            }).catch(function (e) { setError(e.message); });
        };
        if (window.Dialog) Dialog.confirm(S.removeAsk, {okLabel: S.remove, danger: true}).then(function (ok) { if (ok) go(); });
        else go();
    });
})();
