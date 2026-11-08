/* The canvas builder of landing pages (change landing-builder-redesign, #594; epic #348).
 *
 * The canvas is the page as visitors see it. Text marked `data-field` in a block (and
 * `data-page-field` in the hero) is edited in place; everything else lives in the block's panel
 * form, which holds the WHOLE block (canvas text travels in hidden fields of that form). Every
 * change posts the panel form with `autosave=1`; the answer carries the re-rendered canvas block,
 * outline row and panel, swapped in unless the creator is typing there. Add, duplicate and
 * delete are plain posts. Fragments come from the server (rendered and escaped by Django) and are
 * parsed with DOMParser; messages go in with textContent. */
(function () {
  'use strict';

  var root = document.getElementById('lb');
  if (!root) return;
  var MAY_EDIT = root.dataset.mayEdit === '1';
  var T = window.LB_TEXT || {};
  var canvas = document.getElementById('lb-canvas');
  var frame = document.getElementById('lb-frame');
  var blocksEl = document.getElementById('lb-blocks');
  var outline = document.getElementById('lb-outline');
  var panel = document.getElementById('lb-panel');
  var BASES = {};
  try { BASES = JSON.parse(document.getElementById('lb-basemaps').textContent || '{}'); } catch (e) { BASES = {}; }
  Object.keys(BASES).forEach(function (k) {
    if (BASES[k].provider === 'mapbox') BASES[k].opts.accessToken = window.LB_MAPBOX_TOKEN;
  });

  var RICH_TOOLBAR = [['bold', 'italic', 'link'], [{ header: 2 }, { list: 'bullet' }, { list: 'ordered' }], ['clean']];

  function csrf() {
    var i = document.querySelector('input[name=csrfmiddlewaretoken]');
    return i ? i.value : '';
  }

  function parseFragment(html) {
    var doc = new DOMParser().parseFromString('<!DOCTYPE html><body>' + html, 'text/html');
    return document.adoptNode(doc.body.firstElementChild);
  }

  /* ─── save state ─────────────────────────────────────────────────────── */
  var saved = document.getElementById('lb-saved');
  var inflight = 0;
  function status(kind) {
    if (!saved) return;
    var icon = saved.querySelector('i'), text = saved.querySelector('span');
    saved.dataset.state = kind;
    if (kind === 'saving') { icon.className = 'fas fa-circle-notch fa-spin'; text.textContent = T.saving; }
    else if (kind === 'saved') { icon.className = 'fas fa-check-circle'; text.textContent = T.saved; }
    else if (kind === 'failed') { icon.className = 'fas fa-exclamation-triangle'; text.textContent = T.failed; }
    else { icon.className = 'fas fa-exclamation-triangle'; text.textContent = T.offline; }
  }

  /* ─── selection ──────────────────────────────────────────────────────── */
  function select(id, scroll) {
    id = String(id || 'page');
    root.dataset.selected = id;
    document.querySelectorAll('.lb-blk').forEach(function (b) { b.classList.toggle('on', b.dataset.block === id); });
    var hero = document.getElementById('lb-hero');
    if (hero) hero.classList.toggle('on', id === 'page');
    document.querySelectorAll('.lb-oi').forEach(function (o) {
      o.classList.toggle('on', (o.dataset.block || 'page') === id);
    });
    var any = false;
    panel.querySelectorAll('.lb-pane').forEach(function (p) {
      var hit = p.dataset.pane === id;
      p.hidden = !hit;
      any = any || hit;
    });
    if (!any) document.getElementById('lb-page-pane').hidden = false;
    try {
      var url = new URL(window.location.href);
      if (id === 'page') url.searchParams.delete('select'); else url.searchParams.set('select', id);
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    } catch (e) { /* old browsers: the URL just does not follow */ }
    if (scroll) {
      var target = id === 'page' ? hero : canvas.querySelector('.lb-blk[data-block="' + id + '"]');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-add-after]')) return;
    var t = e.target.closest('[data-select-target]');
    if (t && !e.target.closest('form')) {
      select(t.dataset.selectTarget, !!t.closest('.lb-rail, .lb-tools'));
      return;
    }
    var blk = e.target.closest('.lb-blk');
    if (blk && !e.target.closest('.lb-tools')) select(blk.dataset.block, false);
    else if (e.target.closest('#lb-hero')) select('page', false);
  });
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('.lb-oi')) {
      e.preventDefault();
      select(e.target.dataset.selectTarget || e.target.dataset.block, true);
    }
  });

  // Links inside the canvas are the visitor's: never follow them here.
  canvas.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (a && !a.closest('.lb-tools')) e.preventDefault();
  });

  /* ─── editable text ──────────────────────────────────────────────────── */
  var plainMode = (function () {
    var d = document.createElement('div');
    d.setAttribute('contenteditable', 'plaintext-only');
    return d.contentEditable === 'plaintext-only' ? 'plaintext-only' : 'true';
  })();

  function plainValue(el) { return (el.innerText || '').replace(/[ \t]+\n/g, '\n').trim(); }

  function newQuill(host, html, onChange) {
    var q = new Quill(host, { theme: 'bubble', placeholder: host.dataset.placeholder || '', modules: { toolbar: RICH_TOOLBAR } });
    q.setContents(q.clipboard.convert({ html: html || '' }), 'silent');
    q.on('text-change', function (d, o, source) { if (source === 'user') onChange(); });
    host._quill = q;
    return q;
  }

  function mountRich(el, onChange) {
    if (typeof Quill === 'undefined' || el.dataset.mounted) return;
    el.dataset.mounted = '1';
    var html = el.innerHTML;          // the server-sanitised body, read only
    el.textContent = '';
    newQuill(el, html, onChange);
  }

  function richValue(el) {
    if (!el._quill) return el.innerHTML;
    var html = el._quill.root.innerHTML;
    return html === '<p><br></p>' ? '' : html;
  }

  function initBlockEditing(blk) {
    var id = blk.dataset.block;
    blk.querySelectorAll('form').forEach(function (f) { if (!f.closest('.lb-tools')) f.setAttribute('inert', ''); });
    if (!MAY_EDIT) return;
    blk.querySelectorAll('[data-field]').forEach(function (el) {
      if (el.matches('[data-rich]')) {
        mountRich(el, function () { queueBlock(id); });
        return;
      }
      el.setAttribute('contenteditable', plainMode);
      el.addEventListener('input', function () { queueBlock(id); });
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !el.matches('.lp-event-desc, .lp-survey-desc')) { e.preventDefault(); el.blur(); }
      });
      el.addEventListener('blur', function () { if (timers[id]) flushBlock(id); });
    });
  }

  function initHero() {
    var hero = document.getElementById('lb-hero');
    if (!hero || !MAY_EDIT) return;
    hero.querySelectorAll('[data-page-field]').forEach(function (el) {
      el.setAttribute('contenteditable', plainMode);
      el.addEventListener('input', queuePage);
      el.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); el.blur(); } });
      el.addEventListener('blur', function () { if (pageTimer) flushPage(); });
    });
  }

  /* ─── maps and results on the canvas ─────────────────────────────────── */
  var maps = new WeakMap();
  function initVisuals(blk) {
    if (typeof L !== 'undefined') {
      blk.querySelectorAll('.lp-map[data-color]').forEach(function (el) {
        var src = document.getElementById('area-' + el.id.replace('map-', 'b-'));
        if (!src || maps.has(el)) return;
        var base = BASES[el.dataset.basemap] || BASES.streets || BASES[Object.keys(BASES)[0]];
        var map = L.map(el, { scrollWheelZoom: false });
        if (base) L.tileLayer(base.url, Object.assign({}, base.opts)).addTo(map);
        var color = el.dataset.color || '#2f6fb0';
        var layer = L.geoJSON(JSON.parse(src.textContent), {
          style: function () { return { color: color, weight: 3, fillOpacity: 0.15 }; },
          pointToLayer: function (f, ll) { return L.circleMarker(ll, { radius: 7, color: color, weight: 2, fillOpacity: 0.8 }); }
        }).addTo(map);
        map.fitBounds(layer.getBounds(), { padding: [24, 24], maxZoom: 17 });
        maps.set(el, map);
      });
    }
    if (blk.dataset.kind === 'results' && window.renderResultBlocks) {
      var data = blk.querySelector('script[id^="res-"]');
      if (data) {
        try { window.renderResultBlocks([JSON.parse(data.textContent)], BASES); } catch (e) { /* the holder stays empty */ }
      }
    }
  }
  function dropVisuals(blk) {
    blk.querySelectorAll('.lp-map').forEach(function (el) {
      var m = maps.get(el);
      if (m) { m.remove(); maps.delete(el); }
    });
  }
  function resizeMaps() {
    canvas.querySelectorAll('.lp-map').forEach(function (el) { var m = maps.get(el); if (m) m.invalidateSize(); });
  }

  /* ─── panel forms ────────────────────────────────────────────────────── */
  function blockForm(id) { return panel.querySelector('.lb-pane[data-pane="' + id + '"] form.lb-form'); }
  function pageForm() { return panel.querySelector('.lb-page-form'); }

  function renumberPhases(form) {
    form.querySelectorAll('.lb-rows[data-row-kind=timeline] .lb-row').forEach(function (row, i) {
      var r = row.querySelector('input[name=current]');
      if (r) r.value = String(i);
    });
  }

  function syncBlock(id) {
    var form = blockForm(id), blk = canvas.querySelector('.lb-blk[data-block="' + id + '"]');
    if (!form || !blk) return;
    blk.querySelectorAll('[data-field]').forEach(function (el) {
      var input = form.querySelector('[name="' + el.dataset.field + '"]');
      if (input) input.value = el.matches('[data-rich]') ? richValue(el) : plainValue(el);
    });
    form.querySelectorAll('textarea[data-rich]').forEach(function (t) { if (t._host) t.value = richValue(t._host); });
    renumberPhases(form);
  }

  function bindRichTextarea(t, onChange) {
    if (t._host || typeof Quill === 'undefined') return;
    var host = document.createElement('div');
    host.className = 'lb-rich-field';
    host.dataset.placeholder = t.getAttribute('placeholder') || '';
    t.parentNode.insertBefore(host, t.nextSibling);
    newQuill(host, t.value, onChange);
    t.style.display = 'none';
    t._host = host;
  }

  function initPanelForm(form, id) {
    if (!form || form.dataset.bound || !MAY_EDIT) return;
    form.dataset.bound = '1';
    var isPage = form.classList.contains('lb-page-form');
    var later = isPage ? queuePage : function () { queueBlock(id); };
    var now = isPage ? flushPage : function (force) { flushBlock(id, force); };
    form.addEventListener('submit', function (e) { e.preventDefault(); now(true); });
    form.addEventListener('input', function (e) {
      if (e.target.matches('input[type=text], input:not([type]), input[type=url], input[type=number], input[type=email], textarea')) later();
    });
    form.addEventListener('change', function (e) {
      var t = e.target;
      if (t.dataset.autosave === 'change' || t.matches('select, input[type=checkbox], input[type=radio], input[type=color], input[type=date], input[type=time], input[type=file]')) {
        now(t.type === 'file' || t.type === 'checkbox');
      }
    });
    form.querySelectorAll('textarea[data-rich]').forEach(function (t) { bindRichTextarea(t, later); });
    var add = form.querySelector('.lb-row-add'), tpl = form.querySelector('template.lb-row-template'),
        rows = form.querySelector('.lb-rows');
    if (add && tpl && rows) {
      add.addEventListener('click', function () {
        var node = tpl.content.firstElementChild.cloneNode(true);
        rows.appendChild(node);
        node.querySelectorAll('textarea[data-rich]').forEach(function (t) { bindRichTextarea(t, later); });
        var first = node.querySelector('input');
        if (first) first.focus();
      });
    }
    form.addEventListener('click', function (e) {
      var rm = e.target.closest('.lb-row-remove');
      if (!rm) return;
      if (form.querySelectorAll('.lb-rows .lb-row').length > 1) { rm.closest('.lb-row').remove(); now(); }
    });
  }

  function showErrors(form, errors) {
    var box = form && form.querySelector('.lb-errors');
    if (!box) return;
    var msgs = Object.keys(errors || {}).map(function (k) { return errors[k]; });
    box.textContent = msgs.join(' ');
    box.hidden = !msgs.length;
  }

  /* ─── autosave ───────────────────────────────────────────────────────── */
  var timers = {}, busy = {}, again = {};

  function queueBlock(id) {
    status('saving');
    clearTimeout(timers[id]);
    timers[id] = setTimeout(function () { flushBlock(id); }, 600);
  }

  function post(url, data) {
    return fetch(url, {
      method: 'POST', body: data, credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' }
    }).then(function (r) {
      return r.json().then(function (body) { return { ok: r.ok && body.ok, status: r.status, body: body }; },
                          function () { return { ok: false, status: r.status, body: {} }; });
    });
  }

  function flushBlock(id, force) {
    clearTimeout(timers[id]);
    timers[id] = null;
    if (busy[id]) { again[id] = again[id] === true || force === true ? true : 'yes'; return; }
    var form = blockForm(id);
    if (!form) return;
    syncBlock(id);
    var data = new FormData(form);
    data.set('autosave', '1');
    busy[id] = true;
    inflight++;
    status('saving');
    post(form.action, data).then(function (res) {
      if (res.ok) {
        showErrors(form, null);
        swapBlock(id, res.body, force === true);
        status(inflight > 1 ? 'saving' : 'saved');
      } else if (res.status === 422) {
        showErrors(form, res.body.errors);
        select(id, false);
        status('failed');
      } else {
        status('offline');
      }
    }).catch(function () { status('offline'); }).then(function () {
      busy[id] = false;
      inflight--;
      if (again[id]) { var f = again[id] === true; again[id] = false; flushBlock(id, f); }
    });
  }

  function focusedIn(el) { return el && document.activeElement && document.activeElement !== document.body && el.contains(document.activeElement); }

  var pendingSwap = {};
  function morePending(id) { return !!timers[id] || !!again[id]; }
  function swapBlock(id, body, force) {
    // More edits already queued for this block: this answer is stale, the next one will swap.
    if (morePending(id) && !force) return;
    var blk = canvas.querySelector('.lb-blk[data-block="' + id + '"]');
    if (blk && body.block) {
      if (focusedIn(blk)) pendingSwap[id] = body.block;   // never under the caret
      else replaceBlock(blk, body.block);
    }
    var row = outline.querySelector('.lb-oi[data-block="' + id + '"]');
    if (row && body.outline) {
      var newRow = parseFragment(body.outline);
      newRow.classList.toggle('on', root.dataset.selected === id);
      row.replaceWith(newRow);
    }
    var pane = panel.querySelector('.lb-pane[data-pane="' + id + '"]');
    if (pane && body.panel && (force || !focusedIn(pane))) {
      var newPane = parseFragment(body.panel);
      newPane.hidden = root.dataset.selected !== id;
      pane.replaceWith(newPane);
      initPanelForm(newPane.querySelector('form.lb-form'), id);
    }
  }

  function replaceBlock(blk, html) {
    var fresh = parseFragment(html);
    fresh.classList.toggle('on', root.dataset.selected === blk.dataset.block);
    dropVisuals(blk);
    blk.replaceWith(fresh);
    initBlockEditing(fresh);
    initVisuals(fresh);
  }

  canvas.addEventListener('focusout', function (e) {
    var blk = e.target.closest && e.target.closest('.lb-blk');
    if (!blk) return;
    setTimeout(function () {
      var id = blk.dataset.block;
      if (pendingSwap[id] && !focusedIn(blk) && !busy[id] && !morePending(id)) {
        var html = pendingSwap[id];
        delete pendingSwap[id];
        if (blk.isConnected) replaceBlock(blk, html);
      }
    }, 0);
  });

  /* page settings */
  var pageTimer = null, pageBusy = false, pageAgain = false;
  function queuePage() { status('saving'); clearTimeout(pageTimer); pageTimer = setTimeout(flushPage, 600); }
  function flushPage(force) {
    clearTimeout(pageTimer);
    pageTimer = null;
    if (pageBusy) { pageAgain = true; return; }
    var form = pageForm();
    if (!form) return;
    var hero = document.getElementById('lb-hero');
    if (hero) {
      hero.querySelectorAll('[data-page-field]').forEach(function (el) {
        var input = form.querySelector('[name="' + el.dataset.pageField + '"]');
        if (input) input.value = plainValue(el);
      });
    }
    var data = new FormData(form);
    data.set('autosave', '1');
    pageBusy = true;
    inflight++;
    status('saving');
    post(form.action, data).then(function (res) {
      if (res.ok) {
        showErrors(form, null);
        var title = document.getElementById('lb-title');
        if (title) title.textContent = res.body.title;
        var url = document.getElementById('lb-url');
        if (url && res.body.public_url) url.value = res.body.public_url;
        var heroNow = document.getElementById('lb-hero');
        if (heroNow && res.body.hero && !focusedIn(heroNow)) {
          var fresh = parseFragment(res.body.hero);
          fresh.classList.toggle('on', root.dataset.selected === 'page');
          heroNow.replaceWith(fresh);
          initHero();
        }
        var pane = document.getElementById('lb-page-pane');
        if (pane && res.body.page_panel && !pageTimer && !pageAgain && (force === true || !focusedIn(pane))) {
          var np = parseFragment(res.body.page_panel);
          np.hidden = root.dataset.selected !== 'page';
          pane.replaceWith(np);
          initPanelForm(np.querySelector('form.lb-form'));
        }
        status(inflight > 1 ? 'saving' : 'saved');
      } else if (res.status === 422) {
        showErrors(form, res.body.errors);
        select('page', false);
        status('failed');
      } else {
        status('offline');
      }
    }).catch(function () { status('offline'); }).then(function () {
      pageBusy = false;
      inflight--;
      if (pageAgain) { pageAgain = false; flushPage(); }
    });
  }

  /* ─── order ──────────────────────────────────────────────────────────── */
  function canvasOrder() {
    return Array.prototype.map.call(blocksEl.querySelectorAll(':scope > .lb-item'), function (i) { return parseInt(i.dataset.block, 10); });
  }
  function applyOrder(order) {
    var end = blocksEl.querySelector(':scope > .lb-end-add');
    order.forEach(function (id) {
      var item = blocksEl.querySelector(':scope > .lb-item[data-block="' + id + '"]');
      if (item) blocksEl.insertBefore(item, end);
      var row = outline.querySelector('.lb-oi[data-block="' + id + '"]');
      if (row) outline.appendChild(row);
    });
    var last = order.length ? String(order[order.length - 1]) : '';
    document.querySelectorAll('.lb-end-add, .lb-add-btn').forEach(function (b) { b.dataset.addAfter = last; });
  }
  function saveOrder(order) {
    status('saving');
    fetch(root.dataset.reorderUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({ order: order })
    }).then(function (r) { status(r.ok ? 'saved' : 'offline'); if (!r.ok) window.location.reload(); })
      .catch(function () { status('offline'); });
  }

  if (MAY_EDIT && typeof Sortable !== 'undefined') {
    Sortable.create(blocksEl, {
      draggable: '.lb-item', handle: '.lb-grab', animation: 150,
      onEnd: function () { var o = canvasOrder(); applyOrder(o); saveOrder(o); }
    });
    Sortable.create(outline, {
      draggable: '.lb-oi', handle: '.lb-oi-h', animation: 150, delay: 300, delayOnTouchOnly: true,
      onEnd: function () {
        var o = Array.prototype.map.call(outline.querySelectorAll('.lb-oi'), function (r) { return parseInt(r.dataset.block, 10); });
        applyOrder(o);
        saveOrder(o);
      }
    });
  }
  canvas.addEventListener('click', function (e) {
    var mv = e.target.closest('[data-move]');
    if (!mv) return;
    var id = parseInt(mv.closest('.lb-blk').dataset.block, 10), o = canvasOrder(), i = o.indexOf(id);
    var j = mv.dataset.move === 'up' ? i - 1 : i + 1;
    if (i < 0 || j < 0 || j >= o.length) return;
    o.splice(i, 1);
    o.splice(j, 0, id);
    applyOrder(o);
    saveOrder(o);
    var blk = canvas.querySelector('.lb-blk[data-block="' + id + '"]');
    if (blk) blk.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  /* ─── block library ──────────────────────────────────────────────────── */
  var lib = document.getElementById('lb-lib'), libBack = document.getElementById('lb-lib-back'),
      libSearch = document.getElementById('lb-lib-search');
  function openLib(after) {
    if (!lib) return;
    document.getElementById('lb-lib-after').value = after || '';
    lib.hidden = false;
    libBack.hidden = false;
    libSearch.value = '';
    filterLib('');
    libSearch.focus();
  }
  function closeLib() { if (lib) { lib.hidden = true; libBack.hidden = true; } }
  function filterLib(q) {
    q = q.trim().toLowerCase();
    lib.querySelectorAll('.lb-tile').forEach(function (t) { t.hidden = !!q && t.dataset.search.indexOf(q) < 0; });
    lib.querySelectorAll('.lb-lib-grp').forEach(function (g) { g.hidden = !g.querySelector('.lb-tile:not([hidden])'); });
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-add-after]');
    if (a && MAY_EDIT) { e.preventDefault(); openLib(a.dataset.addAfter); }
  });
  if (lib) {
    document.getElementById('lb-lib-close').addEventListener('click', closeLib);
    libBack.addEventListener('click', closeLib);
    libSearch.addEventListener('input', function () { filterLib(libSearch.value); });
    libSearch.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var first = lib.querySelector('.lb-tile:not([hidden])');
        if (first) first.click();
      }
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeLib(); closePop(); }
  });

  /* ─── confirmations ──────────────────────────────────────────────────── */
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-confirm]');
    if (f && !window.confirm(f.dataset.confirm)) e.preventDefault();
  });

  /* ─── device width ───────────────────────────────────────────────────── */
  document.querySelectorAll('#lb-device button').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('#lb-device button').forEach(function (o) { o.classList.toggle('on', o === b); });
      frame.classList.toggle('mobile', b.dataset.width === 'mobile');
      setTimeout(resizeMaps, 280);
    });
  });

  /* ─── publish popover ────────────────────────────────────────────────── */
  var pop = document.getElementById('lb-pop'), popBtn = document.getElementById('lb-pub-btn');
  function closePop() { if (pop) { pop.hidden = true; popBtn.setAttribute('aria-expanded', 'false'); } }
  if (pop) {
    popBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      pop.hidden = !pop.hidden;
      popBtn.setAttribute('aria-expanded', pop.hidden ? 'false' : 'true');
    });
    document.addEventListener('click', function (e) { if (!pop.hidden && !e.target.closest('.lb-pub')) closePop(); });
    var copy = document.getElementById('lb-copy');
    copy.addEventListener('click', function () {
      var input = document.getElementById('lb-url');
      input.select();
      var done = function () { copy.title = T.copied; };
      if (navigator.clipboard) navigator.clipboard.writeText(input.value).then(done, function () {});
      else { document.execCommand('copy'); done(); }
    });
    var listed = document.getElementById('lb-listed');
    if (listed) {
      listed.addEventListener('change', function () {
        var form = pageForm(), sel = form && form.querySelector('[name=visibility]');
        if (sel) { sel.value = listed.checked ? 'public' : 'unlisted'; flushPage(true); }
      });
    }
  }

  /* ─── start ──────────────────────────────────────────────────────────── */
  canvas.querySelectorAll('.lb-blk').forEach(function (blk) { initBlockEditing(blk); initVisuals(blk); });
  initHero();
  panel.querySelectorAll('.lb-pane').forEach(function (p) {
    initPanelForm(p.querySelector('form.lb-form'), p.dataset.pane);
  });
  select(root.dataset.selected, root.dataset.selected !== 'page');
  window.addEventListener('beforeunload', function (e) {
    var pending = inflight > 0 || pageTimer || Object.keys(timers).some(function (k) { return timers[k]; });
    if (pending) { e.preventDefault(); e.returnValue = ''; }
  });
})();
