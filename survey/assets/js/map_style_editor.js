/* The style editor (change map-styles-editor, #543). State is the flat form values of
   survey/map_styles/controls.py; every change posts them to preview.json and repaints
   the MapLibre map with the answer. Save posts the same values; the page then polls the
   version status until the worker has published it. */
(function () {
  'use strict';
  var stateEl = document.getElementById('mse-state');
  if (!stateEl || typeof maplibregl === 'undefined') return;
  var S = JSON.parse(stateEl.textContent);
  var values = S.values;
  var csrf = document.querySelector('#mse-form [name=csrfmiddlewaretoken]').value;
  var dirty = false;
  var map = null;
  var previewTimer = null;
  var previewSeq = 0;
  var i18n = S.i18n || {};
  var HEX = /^#[0-9a-fA-F]{6}$/;

  // ── contrast (greyscale luminance, Rec. 709 like the generator) ──
  function lum(hex) {
    if (!HEX.test(hex || '')) return null;
    var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  }
  // A colour left to the base is judged by the colour the base really draws.
  function effective(role) {
    if (values[role]) return values[role];
    var p = S.controls.palettes.filter(function (x) { return x.key === role; })[0];
    return (p && p.base) || '';
  }
  function roadCasing() {
    if (values.roads === 'custom') return (values.roads_custom || {}).casing || null;
    if (values.roads === 'base') return null;
    var p = S.controls.roads.filter(function (r) { return r.key === values.roads; })[0];
    return p ? p.triple.casing : null;
  }
  function updateWarnings() {
    var land = lum(effective('land'));
    var checks = { park: effective('park'), water: effective('water'), boundary: effective('boundary'),
                   labels_major: effective('labels_major'), labels_minor: effective('labels_minor'), roads: roadCasing() };
    Object.keys(checks).forEach(function (key) {
      var el = document.querySelector('[data-warning-for="' + key + '"]');
      if (!el) return;
      var l = lum(checks[key]);
      // 0.08: Paper A's own parks (#dcefd2 on white, 0.087) pass; really pale colours warn.
      el.hidden = !(land !== null && l !== null && Math.abs(land - l) < 0.08);
    });
  }

  // ── preview ──
  function requestPreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(fetchPreview, 300);
  }
  function fetchPreview() {
    var seq = ++previewSeq;
    var note = document.getElementById('mse-map-note');
    return fetch(S.urls.preview, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(values)
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
      .then(function (res) {
        if (seq !== previewSeq) return;
        if (!res.ok || !res.json.style) {
          note.textContent = (res.json && res.json.error === 'preview unavailable') ? i18n.unavailable : (res.json.error || '');
          note.hidden = false;
          return;
        }
        note.hidden = true;
        if (!map) {
          map = new maplibregl.Map({ container: 'mse-map', style: res.json.style, attributionControl: { compact: true } });
          map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
          frameSurvey();
        } else {
          map.setStyle(res.json.style, { diff: true });
        }
      }).catch(function () { note.textContent = i18n.unavailable; note.hidden = false; });
  }

  // ── survey frame ──
  function currentSurvey() {
    var sel = document.getElementById('mse-survey');
    var uuid = sel ? sel.value : '';
    return S.surveys.filter(function (s) { return s.uuid === uuid; })[0] || S.surveys[0];
  }
  // A searched place replaces the survey's frame until another survey is picked.
  var place = null;
  function currentFrame() { return place || currentSurvey(); }
  function frameSurvey() {
    place = null;
    var search = document.querySelector('#mse-search input');
    if (search) search.value = '';
    var s = currentSurvey();
    if (map && s) map.jumpTo({ center: [s.lng, s.lat], zoom: s.zoom });
    updatePrint();
  }

  // ── place search: the shared control speaks Leaflet ([lat, lng], south-west first) ──
  function attachSearch() {
    var box = document.getElementById('mse-search');
    if (!box || !window.MapPlaceSearch) return;
    var adapter = {
      getCenter: function () {
        if (map) return map.getCenter();
        var s = currentFrame();
        return s ? { lat: s.lat, lng: s.lng } : { lat: 0, lng: 0 };
      },
      fitBounds: function (b) {
        if (map) map.fitBounds([[b[0][1], b[0][0]], [b[1][1], b[1][0]]], { duration: 0, maxZoom: 17 });
      },
      flyTo: function (latlng, zoom) {
        if (map) map.jumpTo({ center: [latlng[1], latlng[0]], zoom: zoom });
      }
    };
    window.MapPlaceSearch.attach(adapter, {
      accessToken: S.token, container: box,
      language: document.documentElement.lang || '',
      labels: { placeholder: box.dataset.placeholder },
      onSelect: function () {
        if (!map) return;
        var c = map.getCenter();
        place = { lng: c.lng, lat: c.lat, zoom: map.getZoom() };
        updatePrint();
      }
    });
  }

  // ── print tab ──
  function updatePrint() {
    var img = document.getElementById('mse-print');
    var note = document.getElementById('mse-print-note');
    var v = S.version;
    var s = currentFrame();
    if (!v.ready_style_id || !s) {
      img.removeAttribute('src');
      note.textContent = i18n.noPrint;
      return;
    }
    var zoom = Math.max(0, Math.round(s.zoom) - 1);  // Static Images zoom is 512-px based
    img.src = 'https://api.mapbox.com/styles/v1/' + v.ready_style_id + '/static/' + s.lng.toFixed(5) + ',' + s.lat.toFixed(5) + ',' + zoom +
      '/' + S.frame[0] + 'x' + S.frame[1] + '@2x?fresh=true&attribution=false&logo=false&access_token=' + encodeURIComponent(S.token);
    if (v.latest_status === 'pending') note.textContent = i18n.printPending.replace('%n', v.latest_number);
    else if (dirty) note.textContent = i18n.printUnsaved;
    else note.textContent = i18n.printVersion.replace('%n', v.ready_number);
  }

  // ── status polling after a save ──
  function pollStatus() {
    fetch(S.urls.status, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (v) {
      S.version = v;
      var status = document.getElementById('mse-status');
      var save = document.getElementById('mse-save');
      if (v.latest_status === 'pending') {
        status.textContent = i18n.publishing;
        save.disabled = true;
        setTimeout(pollStatus, 3000);
      } else if (v.latest_status === 'failed') {
        status.textContent = i18n.failed + (v.latest_error ? ' — ' + v.latest_error : '');
        save.disabled = false;
      } else {
        status.textContent = i18n.published.replace('%n', v.ready_number);
        save.disabled = false;
      }
      updatePrint();
    });
  }

  // ── save ──
  function save() {
    var btn = document.getElementById('mse-save');
    btn.disabled = true;
    fetch(S.urls.save, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ name: document.getElementById('mse-name').value, settings: values })
    }).then(function (r) { return r.json().then(function (j) { return { status: r.status, json: j }; }); })
      .then(function (res) {
        if (res.status === 200 && res.json.ok) {
          dirty = false;
          document.getElementById('mse-unsaved').hidden = true;
          S.version = res.json.version;
          pollStatus();
        } else if (res.status === 409) {
          document.getElementById('mse-status').textContent = res.json.message || i18n.publishing;
          pollStatus();
        } else if (res.status === 403) {
          window.location.reload();
        } else {
          btn.disabled = false;
          var errors = (res.json && res.json.errors) || {};
          Object.keys(errors).forEach(function (k) {
            var hex = document.querySelector('.mse-color[data-key="' + k + '"]');
            if (hex) { hex.closest('.mse-hex').classList.add('is-invalid'); hex.closest('.mse-hex').title = errors[k]; }
          });
        }
      }).catch(function () { btn.disabled = false; });
  }

  // ── wiring ──
  function setValue(key, value) {
    values[key] = value;
    dirty = true;
    document.getElementById('mse-unsaved').hidden = false;
    updateWarnings();
    requestPreview();
    updatePrint();
  }
  document.querySelectorAll('#mse-controls input[type=checkbox][data-key]').forEach(function (cb) {
    cb.addEventListener('change', function () {
      if (cb.dataset.key === 'buildings') document.getElementById('mse-buildings-zoom').hidden = !cb.checked;
      setValue(cb.dataset.key, cb.checked);
    });
  });
  document.querySelectorAll('#mse-controls input[type=radio][data-key]').forEach(function (rb) {
    rb.addEventListener('change', function () { if (rb.checked) setValue(rb.dataset.key, rb.value); });
  });
  document.querySelectorAll('#mse-controls input[type=range][data-key]').forEach(function (range) {
    var out = document.querySelector('[data-output-for="' + range.dataset.key + '"]');
    range.addEventListener('input', function () {
      var noLimit = out && out.dataset.noLimit && range.value === out.dataset.noLimit;
      if (out) out.textContent = noLimit ? out.dataset.noLimitLabel : range.value;
      setValue(range.dataset.key, parseInt(range.value, 10));
    });
  });
  // Colours: a swatch, or the native picker that opens when the code is clicked
  // (owner, 2026-11-07); ↺ returns the role to the base's own colour (empty value).
  document.querySelectorAll('.mse-palette').forEach(function (pal) {
    var role = pal.dataset.role;
    var picker = pal.querySelector('.mse-color');
    var text = pal.querySelector('.mse-hex-text');
    var dot = pal.querySelector('.mse-hex-dot');
    var reset = pal.querySelector('.mse-reset');
    var base = picker.dataset.base || '';
    var hex = pal.querySelector('.mse-hex');
    var pickTitle = hex.title;
    function show(v) {
      text.textContent = v || base || i18n.asBase || 'As base';
      dot.style.background = v || base || 'transparent';
      hex.classList.toggle('is-base', !v);
      if (!v) { hex.title = i18n.baseColour || ''; if (base) picker.value = base; }
      else hex.title = pickTitle;
      reset.hidden = !v;
      pal.querySelectorAll('.mse-swatch').forEach(function (sw) {
        sw.classList.toggle('active', !!v && sw.dataset.colour.toLowerCase() === v.toLowerCase());
      });
    }
    function pick(v) {
      if (v) picker.value = v;
      show(v);
      setValue(role, v);
    }
    pal.querySelectorAll('.mse-swatch').forEach(function (sw) {
      sw.addEventListener('click', function () { pick(sw.dataset.colour.toLowerCase()); });
    });
    picker.addEventListener('input', function () {
      if (HEX.test(picker.value)) pick(picker.value.toLowerCase());
    });
    reset.addEventListener('click', function () { pick(''); });
    show(values[role] || '');
  });
  document.getElementById('mse-name').addEventListener('input', function () {
    dirty = true; document.getElementById('mse-unsaved').hidden = false;
  });
  document.getElementById('mse-save').addEventListener('click', save);
  document.getElementById('mse-survey').addEventListener('change', frameSurvey);
  document.querySelectorAll('.mse-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      document.querySelectorAll('.mse-tab').forEach(function (t) { t.classList.toggle('active', t === tab); });
      document.getElementById('mse-pane-online').hidden = tab.dataset.tab !== 'online';
      document.getElementById('mse-pane-print').hidden = tab.dataset.tab !== 'print';
      if (tab.dataset.tab === 'online' && map) map.resize();
      if (tab.dataset.tab === 'print') updatePrint();
    });
  });
  document.getElementById('mse-photocopy').addEventListener('change', function (e) {
    document.getElementById('mse-print').classList.toggle('mse-grey', e.target.checked);
  });
  window.addEventListener('beforeunload', function (e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

  updateWarnings();
  attachSearch();
  fetchPreview();
  if (document.getElementById('mse-status').dataset.pending === '1') pollStatus();
  window._mse = { values: values, map: function () { return map; }, state: S };
})();
