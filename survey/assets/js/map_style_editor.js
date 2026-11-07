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
  function roadCasing() {
    var p = S.controls.roads.filter(function (r) { return r.key === values.roads; })[0];
    return p ? p.triple.casing : '#8f8f8f';
  }
  function updateWarnings() {
    var land = lum(values.land);
    var checks = { park: values.park, water: values.water, boundary: values.boundary,
                   labels_major: values.labels_major, labels_minor: values.labels_minor, roads: roadCasing() };
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
  function frameSurvey() {
    var s = currentSurvey();
    if (map && s) map.jumpTo({ center: [s.lng, s.lat], zoom: s.zoom });
    updatePrint();
  }

  // ── print tab ──
  function updatePrint() {
    var img = document.getElementById('mse-print');
    var note = document.getElementById('mse-print-note');
    var v = S.version;
    var s = currentSurvey();
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
            var hex = document.querySelector('.mse-hex[data-key="' + k + '"]');
            if (hex) { hex.classList.add('is-invalid'); hex.title = errors[k]; }
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
    cb.addEventListener('change', function () { setValue(cb.dataset.key, cb.checked); });
  });
  document.querySelectorAll('#mse-controls input[type=radio][data-key]').forEach(function (rb) {
    rb.addEventListener('change', function () { if (rb.checked) setValue(rb.dataset.key, rb.value); });
  });
  var range = document.querySelector('#mse-controls input[type=range][data-key]');
  if (range) {
    range.addEventListener('input', function () {
      document.getElementById('mse-zoom-out').textContent = range.value;
      setValue(range.dataset.key, parseInt(range.value, 10));
    });
  }
  document.querySelectorAll('.mse-palette').forEach(function (pal) {
    var role = pal.dataset.role;
    var hex = pal.querySelector('.mse-hex');
    function mark() {
      pal.querySelectorAll('.mse-swatch').forEach(function (sw) {
        sw.classList.toggle('active', sw.dataset.colour.toLowerCase() === String(values[role]).toLowerCase());
      });
    }
    pal.querySelectorAll('.mse-swatch').forEach(function (sw) {
      sw.addEventListener('click', function () {
        hex.value = sw.dataset.colour; hex.classList.remove('is-invalid');
        setValue(role, sw.dataset.colour); mark();
      });
    });
    hex.addEventListener('input', function () {
      var v = hex.value.trim();
      if (HEX.test(v)) { hex.classList.remove('is-invalid'); setValue(role, v.toLowerCase()); mark(); }
      else hex.classList.add('is-invalid');
    });
    mark();
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
  fetchPreview();
  if (document.getElementById('mse-status').dataset.pending === '1') pollStatus();
  window._mse = { values: values, map: function () { return map; }, state: S };
})();
