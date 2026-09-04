/* Object editor for a reference layer (overlay-features, spec layer-object-editor).
 *
 * Three columns: a virtualised list, a Leaflet map with Leaflet.draw, an object
 * card that autosaves. Everything talks JSON to survey/layer_object_views.py;
 * every mutation there rebuilds the derived GeoJSON, so the map here re-reads
 * geometry from the same gated endpoint respondents use.
 *
 * Markup is built with template strings; every value that came from the server
 * or the creator goes through esc(). The one raw assignment is the object
 * description into Quill, which is HTML that already passed coerce_creator_html
 * on the server — the same contract as the Thanks-page editor.
 */
(function () {
    'use strict';
    var root = document.getElementById('loe');
    if (!root || typeof L === 'undefined') return;

    var urls = JSON.parse(root.dataset.urls);
    var layerColor = root.dataset.color || '#2c7be5';
    var csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
    var ROW_H = 38;
    var LABEL_ZOOM_THRESHOLD = 50;   // objects; above this labels show only when zoomed in

    // ---- state ----------------------------------------------------------------
    var objects = JSON.parse(document.getElementById('loe-objects').textContent || '[]');
    var byKey = {};
    objects.forEach(function (o) { byKey[o.key] = o; });
    var filter = { q: '', category: null, problem: null };
    var selected = new Set();       // bulk selection (keys)
    var current = null;             // key of the object in the card
    var visible = [];               // filtered keys, list order
    var features = {};              // key -> leaflet layer
    var featureGroup = L.featureGroup().addTo(map);
    var editingFeature = null;
    var quill = null;
    var detailCache = {};

    // ---- helpers --------------------------------------------------------------
    function u(name, key, extra) {
        var s = urls[name].replace('KEY', encodeURIComponent(key || ''));
        if (extra !== undefined) s = s.replace(/\/0\/$/, '/' + extra + '/');
        return s;
    }
    function api(url, opts) {
        opts = opts || {};
        var headers = { 'X-CSRFToken': csrf };
        var body = opts.body;
        if (body && !(body instanceof FormData)) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(body); }
        return fetch(url, { method: opts.method || 'GET', headers: headers, body: body, credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status)); return d; }); });
    }
    var statusEl = document.getElementById('loe-status');
    var statusTimer = null;
    function status(kind, text) {
        statusEl.className = 'loe-status ' + kind;
        statusEl.textContent = text;
        clearTimeout(statusTimer);
        if (kind === 'saved') statusTimer = setTimeout(function () { statusEl.textContent = ''; }, 2500);
    }
    function debounce(fn, ms) { var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); }; }
    function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
    function setHtml(el, html) { el.innerHTML = html; }   // callers pass esc()-built markup only
    function applySummary(s) {
        if (!s) return;
        document.getElementById('loe-count').textContent = s.object_count;
        document.getElementById('loe-nophoto').textContent = s.without_photo;
        document.getElementById('loe-notext').textContent = s.without_text;
        renderChips();
        document.getElementById('loe-empty').hidden = s.object_count > 0;
    }
    function upsertRow(row) {
        var existing = byKey[row.key];
        if (existing) { Object.assign(existing, row); }
        else { objects.push(row); byKey[row.key] = row; }
        recomputeVisible();
    }

    // ---- chips ----------------------------------------------------------------
    function categories() {
        var set = {};
        objects.forEach(function (o) { if (o.category) set[o.category] = (set[o.category] || 0) + 1; });
        return set;
    }
    function renderChips() {
        var cats = categories();
        var html = '<span class="loe-chip' + (filter.category === null && !filter.problem ? ' on' : '') + '" data-all="1">All · ' + objects.length + '</span>';
        Object.keys(cats).sort().forEach(function (c) {
            html += '<span class="loe-chip' + (filter.category === c ? ' on' : '') + '" data-cat="' + esc(c) + '">' + esc(c) + ' · ' + cats[c] + '</span>';
        });
        var noPhoto = objects.filter(function (o) { return !(o.assets && o.assets.image); }).length;
        var noText = objects.filter(function (o) { return !o.has_text; }).length;
        html += '<span class="loe-chip warn' + (filter.problem === 'photo' ? ' on' : '') + '" data-problem="photo"><i class="fas fa-image"></i> no photo · ' + noPhoto + '</span>';
        html += '<span class="loe-chip warn' + (filter.problem === 'text' ? ' on' : '') + '" data-problem="text"><i class="fas fa-align-left"></i> no text · ' + noText + '</span>';
        setHtml(document.getElementById('loe-chips'), html);
        setHtml(document.getElementById('loe-categories'), Object.keys(cats).map(function (c) { return '<option value="' + esc(c) + '">'; }).join(''));
    }
    document.getElementById('loe-chips').addEventListener('click', function (e) {
        var chip = e.target.closest('.loe-chip'); if (!chip) return;
        if (chip.dataset.all) { filter.category = null; filter.problem = null; }
        else if (chip.dataset.cat) { filter.category = filter.category === chip.dataset.cat ? null : chip.dataset.cat; }
        else if (chip.dataset.problem) { filter.problem = filter.problem === chip.dataset.problem ? null : chip.dataset.problem; }
        renderChips(); recomputeVisible();
    });
    document.getElementById('loe-search').addEventListener('input', debounce(function (e) {
        filter.q = e.target.value.trim().toLowerCase(); recomputeVisible();
    }, 120));

    // ---- list (virtualised) -----------------------------------------------------
    var rowsEl = document.getElementById('loe-rows');
    var spacer = document.createElement('div'); spacer.style.position = 'relative';
    rowsEl.appendChild(spacer);

    function matches(o) {
        if (filter.q && (o.title + ' ' + o.key + ' ' + (o.category || '')).toLowerCase().indexOf(filter.q) === -1) return false;
        if (filter.category && o.category !== filter.category) return false;
        if (filter.problem === 'photo' && o.assets && o.assets.image) return false;
        if (filter.problem === 'text' && o.has_text) return false;
        return true;
    }
    function recomputeVisible() {
        var sorted = objects.slice().sort(function (a, b) { return (a.title || a.key).localeCompare(b.title || b.key, undefined, { numeric: true }); });
        visible = sorted.filter(matches).map(function (o) { return o.key; });
        var visibleSet = new Set(visible);
        Object.keys(features).forEach(function (k) { styleFeature(k, visibleSet.has(k)); });
        renderRows();
    }
    function renderRows() {
        spacer.style.height = (visible.length * ROW_H) + 'px';
        var start = Math.max(0, Math.floor(rowsEl.scrollTop / ROW_H) - 5);
        var end = Math.min(visible.length, start + Math.ceil(rowsEl.clientHeight / ROW_H) + 10);
        var html = '';
        for (var i = start; i < end; i++) {
            var o = byKey[visible[i]];
            var meta = [];
            if (o.category) meta.push(esc(o.category));
            if (o.assets) Object.keys(o.assets).forEach(function (k) {
                var icon = { image: 'fa-image', audio: 'fa-microphone', document: 'fa-file-alt', video: 'fa-video', embed: 'fa-video' }[k];
                if (icon) meta.push('<i class="fas ' + icon + '"></i>' + o.assets[k]);
            });
            var miss = !(o.assets && o.assets.image) || !o.has_text;
            html += '<div class="loe-row' + (o.key === current ? ' sel' : '') + (miss ? ' miss' : '') + '" data-key="' + esc(o.key) + '" style="position:absolute;top:' + (i * ROW_H) + 'px;left:0;right:0;">' +
                '<input type="checkbox" class="loe-cb"' + (selected.has(o.key) ? ' checked' : '') + '>' +
                '<span class="sw" style="background:' + esc(layerColor) + '"></span>' +
                '<span class="t" title="' + esc(o.title) + '">' + esc(o.title || o.key) + '</span>' +
                '<span class="m">' + meta.join(' · ') + '</span></div>';
        }
        setHtml(spacer, html);
        document.getElementById('loe-range').textContent = visible.length ? (start + 1) + '–' + end + ' of ' + visible.length : '0';
    }
    rowsEl.addEventListener('scroll', renderRows);
    window.addEventListener('resize', renderRows);
    rowsEl.addEventListener('click', function (e) {
        var row = e.target.closest('.loe-row'); if (!row) return;
        var key = row.dataset.key;
        if (e.target.classList.contains('loe-cb')) {
            if (e.target.checked) selected.add(key); else selected.delete(key);
            updateBulk(); return;
        }
        select(key, true);
    });
    rowsEl.addEventListener('keydown', function (e) {
        if (!visible.length) return;
        var idx = visible.indexOf(current);
        if (e.key === 'ArrowDown') { e.preventDefault(); select(visible[Math.min(visible.length - 1, idx + 1)], true); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); select(visible[Math.max(0, idx - 1)], true); }
        else if (e.key === 'Enter' && current) { e.preventDefault(); document.querySelector('#loe-card-form input[data-field=title]').focus(); }
    });
    function scrollRowIntoView(key) {
        var i = visible.indexOf(key); if (i < 0) return;
        var top = i * ROW_H;
        if (top < rowsEl.scrollTop || top + ROW_H > rowsEl.scrollTop + rowsEl.clientHeight) rowsEl.scrollTop = top - rowsEl.clientHeight / 2;
    }

    // ---- bulk -----------------------------------------------------------------
    function updateBulk() {
        var bar = document.getElementById('loe-bulk');
        bar.hidden = selected.size === 0;
        document.getElementById('loe-bulk-count').textContent = selected.size + ' selected';
    }
    document.getElementById('loe-bulk-clear').addEventListener('click', function () { selected.clear(); updateBulk(); renderRows(); });
    document.getElementById('loe-bulk-category').addEventListener('click', function () {
        var cat = window.prompt('Category for ' + selected.size + ' objects:');
        if (cat === null) return;
        api(urls.bulk, { method: 'POST', body: { action: 'set_category', category: cat, keys: Array.from(selected) } }).then(function (d) {
            selected.forEach(function (k) { if (byKey[k]) byKey[k].category = cat; });
            selected.clear(); updateBulk(); applySummary(d.summary); recomputeVisible(); status('saved', 'Saved');
        }).catch(function (e) { status('error', e.message); });
    });
    document.getElementById('loe-bulk-delete').addEventListener('click', function () {
        if (!window.confirm('Delete ' + selected.size + ' objects? Answers about them are removed too.')) return;
        api(urls.bulk, { method: 'POST', body: { action: 'delete', keys: Array.from(selected) } }).then(function (d) {
            selected.forEach(removeLocal); selected.clear(); updateBulk(); applySummary(d.summary); recomputeVisible(); status('saved', 'Deleted');
        }).catch(function (e) { status('error', e.message); });
    });
    function removeLocal(key) {
        objects = objects.filter(function (o) { return o.key !== key; });
        delete byKey[key]; delete detailCache[key];
        if (features[key]) { featureGroup.removeLayer(features[key]); delete features[key]; }
        if (current === key) closeCard();
    }

    // ---- map ------------------------------------------------------------------
    function styleFor(key, isVisible, isCurrent) {
        var dim = !isVisible;
        return { color: isCurrent ? '#c2410c' : (dim ? '#9ca3af' : layerColor), weight: isCurrent ? 4 : 2,
                 fillColor: dim ? '#e5e7eb' : layerColor, fillOpacity: dim ? 0.25 : (isCurrent ? 0.45 : 0.3), opacity: dim ? 0.6 : 1 };
    }
    function styleFeature(key, isVisible) {
        var f = features[key]; if (!f) return;
        var isCurrent = key === current;
        if (f.setStyle) f.setStyle(styleFor(key, isVisible, isCurrent));
        else if (f.setIcon) f.setIcon(markerIcon(isVisible, isCurrent));
        if (isCurrent && f.bringToFront) f.bringToFront();
    }
    function markerIcon(isVisible, isCurrent) {
        var color = isCurrent ? '#c2410c' : (isVisible ? layerColor : '#9ca3af');
        return L.divIcon({ className: '', iconSize: [18, 18], iconAnchor: [9, 9],
            html: '<div style="width:18px;height:18px;border-radius:50%;background:' + esc(color) + ';border:3px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.25)"></div>' });
    }
    function addFeature(geojsonFeature) {
        var key = geojsonFeature.properties._key;
        if (features[key]) featureGroup.removeLayer(features[key]);
        var lyr = L.geoJSON(geojsonFeature, {
            pointToLayer: function (_f, latlng) { return L.marker(latlng, { icon: markerIcon(true, false) }); },
            style: function () { return styleFor(key, true, false); }
        }).getLayers()[0];
        lyr._key = key;
        lyr.on('click', function () { if (!drawing) select(key, false); });
        lyr.bindTooltip(esc(geojsonFeature.properties._title || key), { permanent: true, direction: 'top', className: 'loe-feature-label', offset: [0, -8] });
        features[key] = lyr;
        featureGroup.addLayer(lyr);
        applyLabelVisibility();
        return lyr;
    }
    function applyLabelVisibility() {
        var show = objects.length <= LABEL_ZOOM_THRESHOLD || map.getZoom() >= 15;
        Object.keys(features).forEach(function (k) {
            var t = features[k].getTooltip(); if (!t) return;
            var el = t.getElement(); if (el) el.style.display = show ? '' : 'none';
        });
    }
    map.on('zoomend', applyLabelVisibility);
    function loadGeometry() {
        return fetch(urls.geojson, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (fc) {
            fc.features.forEach(addFeature);
            if (fc.features.length) map.fitBounds(featureGroup.getBounds().pad(0.1));
            recomputeVisible();
        });
    }

    // ---- drawing ----------------------------------------------------------------
    var drawing = false;
    var hint = document.getElementById('loe-hint');
    var drawControl = new L.Control.Draw({
        position: 'topleft',
        draw: { marker: { icon: markerIcon(true, true) }, polyline: { shapeOptions: { color: layerColor } }, polygon: { shapeOptions: { color: layerColor }, allowIntersection: false },
                rectangle: false, circle: false, circlemarker: false },
        edit: false
    });
    map.addControl(drawControl);
    map.on(L.Draw.Event.DRAWSTART, function () { drawing = true; hint.hidden = false; hint.textContent = 'Click the map to add an object · Esc to cancel'; });
    map.on(L.Draw.Event.DRAWSTOP, function () { drawing = false; hint.hidden = true; });
    map.on(L.Draw.Event.CREATED, function (e) {
        var geometry = e.layer.toGeoJSON().geometry;
        api(urls.objects, { method: 'POST', body: { geometry: geometry, title: '' } }).then(function (d) {
            addFeature(featureFromDetail(d.object));
            upsertRow(d.row); applySummary(d.summary);
            select(d.object.key, false, d.object);
            setTimeout(function () { var t = document.querySelector('#loe-card-form input[data-field=title]'); if (t) { t.focus(); t.select(); } }, 50);
            status('saved', 'Object added');
        }).catch(function (err) { status('error', err.message); });
    });
    function featureFromDetail(detail) {
        return { type: 'Feature', properties: { _key: detail.key, _title: detail.title, _category: detail.category }, geometry: detail.geometry };
    }
    document.getElementById('loe-way-draw').addEventListener('click', function () { new L.Draw.Marker(map, drawControl.options.draw.marker).enable(); });

    // Geometry editing of the current feature: Leaflet.draw's per-layer handlers.
    var moveBtn = document.getElementById('loe-move');
    moveBtn.addEventListener('click', function () {
        if (!current || !features[current]) return;
        if (editingFeature) { finishGeometryEdit(true); return; }
        var f = features[current];
        editingFeature = f;
        if (f.editing) f.editing.enable(); else if (f.dragging) f.dragging.enable();
        hint.hidden = false;
        setHtml(hint, 'Move the vertices, then <b style="cursor:pointer" id="loe-geom-done">Done</b> or <span style="cursor:pointer" id="loe-geom-cancel">Cancel</span>');
        moveBtn.textContent = 'Done';
    });
    hint.addEventListener('click', function (e) {
        if (e.target.id === 'loe-geom-done') finishGeometryEdit(true);
        if (e.target.id === 'loe-geom-cancel') finishGeometryEdit(false);
    });
    function finishGeometryEdit(save) {
        var f = editingFeature; if (!f) return;
        if (f.editing) f.editing.disable(); else if (f.dragging) f.dragging.disable();
        editingFeature = null; hint.hidden = true;
        moveBtn.textContent = 'Edit on map';
        if (!save) { reloadFeature(f._key); return; }
        api(u('geometry', f._key), { method: 'POST', body: { geometry: f.toGeoJSON().geometry } }).then(function (d) {
            upsertRow(d.row); delete detailCache[f._key]; status('saved', 'Geometry saved'); showGeometry(f);
        }).catch(function (err) { status('error', err.message); reloadFeature(f._key); });
    }
    function reloadFeature(key) {
        api(u('object', key)).then(function (d) { addFeature(featureFromDetail(d.object)); styleFeature(key, visible.indexOf(key) >= 0); });
    }

    // ---- card -----------------------------------------------------------------
    var cardForm = document.getElementById('loe-card-form');
    var cardEmpty = document.getElementById('loe-card-empty');
    function closeCard() {
        var prev = current; current = null;
        cardForm.hidden = true; cardEmpty.hidden = false;
        if (prev) styleFeature(prev, visible.indexOf(prev) >= 0);
        renderRows();
    }
    document.getElementById('loe-card-close').addEventListener('click', closeCard);
    function select(key, fly, detail) {
        if (editingFeature) finishGeometryEdit(true);
        var prev = current; current = key;
        if (prev && prev !== key) styleFeature(prev, visible.indexOf(prev) >= 0);
        styleFeature(key, true);
        renderRows(); scrollRowIntoView(key);
        var f = features[key];
        if (f && fly) {
            if (f.getBounds) map.fitBounds(f.getBounds().pad(0.5), { maxZoom: 17 }); else map.panTo(f.getLatLng());
        }
        cardEmpty.hidden = true; cardForm.hidden = false;
        var show = function (d) { detailCache[key] = d; fillCard(d); };
        if (detail) show(detail);
        else if (detailCache[key]) show(detailCache[key]);
        else api(u('object', key)).then(function (d) { if (current === key) show(d.object); }).catch(function (e) { status('error', e.message); });
    }
    var filling = false;
    function fillCard(d) {
        filling = true;
        document.getElementById('loe-card-title').textContent = d.title || d.key;
        document.getElementById('loe-key').value = d.key;
        cardForm.querySelector('input[data-field=title]').value = d.title || '';
        cardForm.querySelector('input[data-field=category]').value = d.category || '';
        cardForm.querySelector('input[data-field=link]').value = d.link || '';
        ensureQuill();
        // Server-sanitized creator HTML (coerce_creator_html) — Quill's own contract.
        quill.root.innerHTML = d.description || '';
        renderAssets(d.assets || []);
        if (features[d.key]) showGeometry(features[d.key]); else document.getElementById('loe-geom').textContent = d.geometry ? d.geometry.type : '—';
        filling = false;
    }
    function showGeometry(f) {
        var gj = f.toGeoJSON().geometry, txt = gj.type;
        if (gj.type === 'Point') txt += ' · ' + gj.coordinates[1].toFixed(5) + ', ' + gj.coordinates[0].toFixed(5);
        else if (gj.type === 'LineString') txt += ' · ' + gj.coordinates.length + ' vertices';
        else if (gj.type === 'Polygon') txt += ' · ' + (gj.coordinates[0].length - 1) + ' vertices';
        document.getElementById('loe-geom').textContent = txt;
    }
    var patch = debounce(function (fields) {
        if (!current) return;
        var key = current;
        status('saving', 'Saving…');
        api(u('object', key), { method: 'PATCH', body: fields }).then(function (d) {
            detailCache[key] = d.object; upsertRow(d.row); applySummary(d.summary);
            if (fields.title !== undefined) {
                document.getElementById('loe-card-title').textContent = d.object.title || d.object.key;
                var f = features[key]; if (f && f.getTooltip()) f.setTooltipContent(esc(d.object.title || key));
            }
            status('saved', 'Saved');
        }).catch(function (e) { status('error', 'Not saved — ' + e.message); });
    }, 500);
    cardForm.querySelectorAll('input[data-field]').forEach(function (inp) {
        inp.addEventListener('input', function () { if (filling) return; var f = {}; f[inp.dataset.field] = inp.value; patch(f); });
    });
    function ensureQuill() {
        if (quill) return;
        quill = new Quill('#loe-quill', { theme: 'snow', modules: { toolbar: {
            container: [['bold', 'italic'], [{ list: 'bullet' }, { list: 'ordered' }], ['link', 'image'], ['clean']],
            handlers: { image: function () {
                var input = document.createElement('input'); input.type = 'file'; input.accept = 'image/png,image/jpeg,image/gif,image/webp';
                input.onchange = function () {
                    var file = input.files && input.files[0]; if (!file) return;
                    var fd = new FormData(); fd.append('image', file);
                    api(urls.descriptionImage, { method: 'POST', body: fd }).then(function (d) {
                        var range = quill.getSelection(true);
                        quill.insertEmbed(range.index, 'image', d.url, 'user');
                    }).catch(function (e) { status('error', e.message); });
                };
                input.click();
            } }
        } } });
        quill.on('text-change', function (_d, _o, source) { if (source !== 'user' || filling) return; patch({ description: quill.root.innerHTML }); });
    }

    // ---- assets ---------------------------------------------------------------
    var assetsEl = document.getElementById('loe-assets');
    var assetsSortable = null;
    function renderAssets(assets) {
        var html = assets.map(function (a, i) {
            var th = a.kind === 'image' ? '<span class="th" style="background-image:url(&quot;' + esc(a.url) + '&quot;)"></span>'
                : '<span class="th"><i class="fas ' + ({ audio: 'fa-microphone', document: 'fa-file-alt', video: 'fa-video', embed: 'fa-video' }[a.kind] || 'fa-paperclip') + '"></i></span>';
            var cover = (a.kind === 'image' && !assets.slice(0, i).some(function (x) { return x.kind === 'image'; })) ? ' <span class="badge badge-secondary">cover</span>' : '';
            return '<div class="loe-att" data-id="' + Number(a.id) + '"><i class="fas fa-grip-vertical grip"></i>' + th +
                '<span class="n" title="' + esc(a.title) + '">' + esc(a.title || a.kind) + cover + '</span>' +
                (a.size_bytes ? '<span class="m" style="color:#9ca3af">' + (a.size_bytes / 1048576).toFixed(1) + ' MB</span>' : '') +
                '<i class="fas fa-trash a" data-del="' + Number(a.id) + '" title="Remove"></i></div>';
        }).join('');
        setHtml(assetsEl, html);
        if (assetsSortable) assetsSortable.destroy();
        assetsSortable = Sortable.create(assetsEl, { handle: '.grip', animation: 120, onEnd: function () {
            var order = Array.from(assetsEl.querySelectorAll('.loe-att')).map(function (el) { return el.dataset.id; });
            api(u('reorder', current), { method: 'POST', body: { order: order } }).then(function (d) {
                upsertRow(d.row); delete detailCache[current]; refreshCardAssets(); status('saved', 'Saved');
            }).catch(function (e) { status('error', e.message); });
        } });
    }
    function refreshCardAssets() {
        if (!current) return;
        api(u('object', current)).then(function (d) { detailCache[current] = d.object; renderAssets(d.object.assets || []); upsertRow(d.row); });
    }
    assetsEl.addEventListener('click', function (e) {
        var del = e.target.closest('[data-del]'); if (!del || !current) return;
        api(u('asset', current, del.dataset.del), { method: 'DELETE' }).then(function (d) {
            upsertRow(d.row); delete detailCache[current]; refreshCardAssets(); applySummaryFromRows(); status('saved', 'Removed');
        }).catch(function (err) { status('error', err.message); });
    });
    function applySummaryFromRows() {
        renderChips();
        document.getElementById('loe-nophoto').textContent = objects.filter(function (o) { return !(o.assets && o.assets.image); }).length;
        document.getElementById('loe-notext').textContent = objects.filter(function (o) { return !o.has_text; }).length;
    }
    function uploadFiles(files) {
        if (!current || !files.length) return;
        var key = current, chain = Promise.resolve();
        Array.from(files).forEach(function (file) {
            chain = chain.then(function () {
                var fd = new FormData(); fd.append('file', file);
                status('saving', 'Uploading ' + file.name + '…');
                return api(u('assets', key), { method: 'POST', body: fd }).then(function (d) { upsertRow(d.row); })
                    .catch(function (e) { status('error', file.name + ': ' + e.message); throw e; });
            });
        });
        chain.then(function () { delete detailCache[key]; if (current === key) refreshCardAssets(); applySummaryFromRows(); status('saved', 'Uploaded'); }).catch(function () {});
    }
    var drop = document.getElementById('loe-drop'), fileInput = document.getElementById('loe-file');
    drop.addEventListener('click', function (e) { if (e.target.closest('#loe-embed-link')) return; fileInput.click(); });
    fileInput.addEventListener('change', function () { uploadFiles(fileInput.files); fileInput.value = ''; });
    ['dragenter', 'dragover'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('dragover'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('dragover'); }); });
    drop.addEventListener('drop', function (e) { uploadFiles(e.dataTransfer.files); });
    document.getElementById('loe-embed-link').addEventListener('click', function (e) {
        e.stopPropagation();
        if (!current) return;
        var url = window.prompt('YouTube or Vimeo link:'); if (!url) return;
        var fd = new FormData(); fd.append('embed_url', url);
        api(u('assets', current), { method: 'POST', body: fd }).then(function (d) { upsertRow(d.row); delete detailCache[current]; refreshCardAssets(); status('saved', 'Embedded'); })
            .catch(function (err) { status('error', err.message); });
    });

    // ---- delete / prev / next -----------------------------------------------------
    document.getElementById('loe-delete').addEventListener('click', function () {
        if (!current) return;
        var key = current;
        api(u('answers', key)).then(function (d) {
            var msg = 'Delete "' + (byKey[key].title || key) + '"?' + (d.answers ? ' ' + d.answers + ' answer(s) about it will be removed.' : '');
            if (!window.confirm(msg)) return;
            return api(u('object', key), { method: 'DELETE' }).then(function (r) { removeLocal(key); applySummary(r.summary); recomputeVisible(); status('saved', 'Deleted'); });
        }).catch(function (e) { status('error', e.message); });
    });
    document.getElementById('loe-prev').addEventListener('click', function () { var i = visible.indexOf(current); if (i > 0) select(visible[i - 1], true); });
    document.getElementById('loe-next').addEventListener('click', function () { var i = visible.indexOf(current); if (i >= 0 && i < visible.length - 1) select(visible[i + 1], true); });

    // ---- imports ------------------------------------------------------------------
    var importModal = $('#loe-import-modal'), importMode = 'geojson', importProps = null;
    var importFile = document.getElementById('loe-import-file'), mappingEl = document.getElementById('loe-import-mapping'), reportEl = document.getElementById('loe-import-report');
    function openImport(mode) {
        importMode = mode; importProps = null; importFile.value = ''; reportEl.textContent = ''; mappingEl.hidden = true;
        importFile.multiple = mode === 'photos';
        importFile.accept = mode === 'geojson' ? '.geojson,.json' : mode === 'csv' ? '.csv,.txt' : 'image/*';
        document.getElementById('loe-import-title').textContent = { geojson: 'Import GeoJSON', csv: 'Import CSV', photos: 'Upload photos (matched by filename)' }[mode];
        document.getElementById('loe-import-go').textContent = mode === 'geojson' ? 'Check file' : 'Import';
        importModal.modal('show');
    }
    document.getElementById('loe-btn-import-geojson').addEventListener('click', function () { openImport('geojson'); });
    document.getElementById('loe-btn-import-csv').addEventListener('click', function () { openImport('csv'); });
    document.getElementById('loe-btn-import-photos').addEventListener('click', function () { openImport('photos'); });
    document.getElementById('loe-way-geojson').addEventListener('click', function () { openImport('geojson'); });
    document.getElementById('loe-way-csv').addEventListener('click', function () { openImport('csv'); });
    function fillMapping(props) {
        var defaults = { key: ['id', 'key', 'code'], title: ['name', 'title', 'label'], category: ['category', 'type', 'class'], description: ['description', 'about', 'text'], link: ['url', 'link', 'website'] };
        mappingEl.querySelectorAll('select').forEach(function (sel) {
            var field = sel.dataset.map;
            setHtml(sel, '<option value="">— none —</option>' + props.map(function (p) { return '<option value="' + esc(p) + '">' + esc(p) + '</option>'; }).join(''));
            var guess = props.find(function (p) { return defaults[field].indexOf(p.toLowerCase()) >= 0; });
            if (guess) sel.value = guess;
        });
        mappingEl.hidden = false;
    }
    function renderReport(r) {
        var lines = [];
        if (r.dry_run) lines.push('<b>' + Number(r.features) + '</b> features in the file → <b>' + Number(r.created) + '</b> objects would be created' + (r.collisions.length ? ', <b>' + r.collisions.length + '</b> skipped (key already exists: ' + esc(r.collisions.slice(0, 10).join(', ')) + ')' : '') + '.');
        else {
            if (r.created !== undefined && r.mode !== 'content') lines.push('<b>' + Number(r.created) + '</b> objects created.');
            if (r.updated !== undefined && r.mode === 'content') lines.push('<b>' + Number(r.updated) + '</b> objects updated.');
            if (r.attached !== undefined) lines.push('<b>' + Number(r.attached) + '</b> photos attached.');
            if (r.collisions && r.collisions.length) lines.push(r.collisions.length + ' skipped — key already exists: ' + esc(r.collisions.slice(0, 20).join(', ')));
            if (r.unmatched && r.unmatched.length) lines.push('<span class="text-danger">' + r.unmatched.length + ' unmatched:</span> ' + esc(r.unmatched.slice(0, 20).join(', ')));
            if (r.invalid && r.invalid.length) lines.push('<span class="text-danger">Rows with invalid coordinates:</span> ' + esc(r.invalid.slice(0, 20).join(', ')));
            if (r.rejected && r.rejected.length) lines.push('<span class="text-danger">Rejected:</span> ' + esc(r.rejected.slice(0, 10).join('; ')));
        }
        setHtml(reportEl, lines.map(function (l) { return '<div>' + l + '</div>'; }).join(''));
    }
    document.getElementById('loe-import-go').addEventListener('click', function () {
        var files = importFile.files; if (!files.length) { reportEl.textContent = 'Choose a file first.'; return; }
        var fd = new FormData();
        var url;
        if (importMode === 'geojson') {
            url = urls.importGeojson; fd.append('file', files[0]);
            if (!importProps) fd.append('dry_run', '1');
            mappingEl.querySelectorAll('select').forEach(function (s) { fd.append('map_' + s.dataset.map, s.value); });
        } else if (importMode === 'csv') { url = urls.importCsv; fd.append('file', files[0]); }
        else { url = urls.importPhotos; Array.from(files).forEach(function (f) { fd.append('files', f); }); }
        status('saving', 'Importing…');
        api(url, { method: 'POST', body: fd }).then(function (r) {
            renderReport(r);
            if (importMode === 'geojson' && r.dry_run) {
                importProps = r.properties; fillMapping(r.properties);
                document.getElementById('loe-import-go').textContent = 'Import ' + r.created + ' objects';
                status('saved', 'Checked'); return;
            }
            status('saved', 'Imported');
            return reloadAll();
        }).catch(function (e) { reportEl.textContent = e.message; status('error', e.message); });
    });
    function reloadAll() {
        return api(urls.objects).then(function (d) {
            objects = d.objects; byKey = {}; objects.forEach(function (o) { byKey[o.key] = o; }); detailCache = {};
            applySummary(d.summary);
            featureGroup.clearLayers(); features = {};
            return loadGeometry();
        });
    }

    // ---- boot ---------------------------------------------------------------------
    renderChips(); recomputeVisible(); updateBulk();
    applySummary({ object_count: objects.length, without_photo: objects.filter(function (o) { return !(o.assets && o.assets.image); }).length,
                   without_text: objects.filter(function (o) { return !o.has_text; }).length, categories: Object.keys(categories()) });
    loadGeometry();
})();
