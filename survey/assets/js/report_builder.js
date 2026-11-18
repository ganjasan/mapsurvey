/* What the report builder adds to the canvas builder (change reports-canvas-editor, #731).
 *
 * reports/builder.html runs on js/site_builder.js — selection, writing in place, rows, drops,
 * autosave, order, the library, the device toggle are that script's. This one holds what only a
 * report has: the publish dialog with its checks, unpublish, the PDF / ZIP job, half-width blocks
 * sitting side by side, quotes picked from the answers, and an address that is not saved while it is
 * being typed. Messages go in with textContent. */
(function () {
  'use strict';

  var root = document.getElementById('lb');
  if (!root || !root.classList.contains('rb')) return;
  var T = window.RB_TEXT || {};
  var blocksEl = document.getElementById('lb-blocks');
  var frame = document.getElementById('lb-frame');

  function csrf() {
    var i = document.querySelector('input[name=csrfmiddlewaretoken]');
    return i ? i.value : '';
  }
  function headers() { return { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' }; }

  /* ─── half-width blocks ──────────────────────────────────────────────────
   * Two consecutive half-width blocks that readers see share a row (reports.render.story_rows).
   * The canvas list is flat, so the pairing is a class, recomputed whenever the list changes. */
  function markPairs() {
    var open = null;
    Array.prototype.forEach.call(blocksEl.querySelectorAll(':scope > .lb-item'), function (item) {
      var blk = item.querySelector('.lb-blk');
      item.classList.remove('rb-pair');
      if (!blk || blk.dataset.shown !== '1') return;
      if (blk.dataset.width === 'half') {
        if (open) { open.classList.add('rb-pair'); item.classList.add('rb-pair'); open = null; }
        else open = item;
      } else {
        open = null;
      }
    });
  }
  if (blocksEl && window.MutationObserver) {
    var pending = false;
    new MutationObserver(function () {
      if (pending) return;
      pending = true;
      setTimeout(function () { pending = false; markPairs(); }, 0);
    }).observe(blocksEl, { childList: true, subtree: true });
  }

  /* ─── live numbers: the page shows the number, the author edits the token ─ */
  document.addEventListener('focusin', function (e) {
    var el = e.target.closest && e.target.closest('[data-raw]');
    if (!el || !el.isContentEditable) return;
    if (el.hasAttribute('data-live')) return;       // a key number picked from the menu: never its token
    el.textContent = el.getAttribute('data-raw');
    el.removeAttribute('data-raw');
    el.removeAttribute('title');
  });

  /* ─── a map's frame (change report-map-views): the author moves the map to the part readers
   * should see and keeps it. The view comes from the Leaflet map the shared renderer left on the
   * holder (`_rpMap`); the hidden field in the block is saved as any field written on the canvas. */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-map-keep], [data-map-reset]');
    if (!btn) return;
    var blk = btn.closest('.lb-blk'), input = blk && blk.querySelector('input[data-input="map_frame"]');
    if (!input) return;
    if (btn.hasAttribute('data-map-reset')) {
      input.value = '';
    } else {
      var holder = blk.querySelector('.map-holder'), map = holder && holder._rpMap;
      if (!map) return;
      var b = map.getBounds();
      input.value = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
        .map(function (v) { return v.toFixed(6); }).join(',');
    }
    btn.blur();     // the answer redraws the block, which never happens under the focus
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });

  /* A select whose choice changes what the panel holds (adding a layer to a map): the shared
   * builder never redraws a pane under the focus, so the focus leaves the select before it saves. */
  document.addEventListener('change', function (e) {
    if (e.target.matches && e.target.matches('select[data-save-now]')) e.target.blur();
  }, true);

  /* ─── key numbers: a number of the survey is picked from a menu, never typed as a token
   * (change report-key-numbers). The menu (#rb-num-menu, drawn once when the report has a survey)
   * opens from "Add a number" and from a number that follows the answers. Rows themselves are the
   * shared builder's: a pick fills the row and fires the events its autosave listens to. ───────── */
  var numMenu = document.getElementById('rb-num-menu'), numTarget = null, numPass = false;
  var LIVE = '.numbers [data-row-field="value"][data-live]';

  function closeNum() {
    if (numMenu) numMenu.hidden = true;
    numTarget = null;
  }
  function openNum(anchor, target) {
    numTarget = target;
    numMenu.hidden = false;
    var r = anchor.getBoundingClientRect(), top = r.bottom + 6;
    if (top + numMenu.offsetHeight > window.innerHeight - 8) top = Math.max(8, r.top - numMenu.offsetHeight - 6);
    numMenu.style.top = top + 'px';
    numMenu.style.left = Math.max(8, Math.min(r.left, window.innerWidth - numMenu.offsetWidth - 8)) + 'px';
    var first = numMenu.querySelector('.rb-num-item');
    if (first) first.focus();
  }
  function setLive(el, item) {
    el.textContent = item.dataset.shown;
    el.setAttribute('data-raw', item.dataset.token);
    el.setAttribute('data-live', '');
  }
  function saveRow(el) {
    el.dispatchEvent(new Event('input', { bubbles: true }));   // queues the block's autosave
    el.dispatchEvent(new Event('blur'));                       // and sends it now
  }
  function isStockLabel(text) {
    text = text.trim();
    if (!text) return true;
    return Array.prototype.some.call(numMenu.querySelectorAll('[data-label]'), function (b) { return b.dataset.label === text; });
  }
  // What the menu was opened for, by block id and row number — never by node: the builder swaps a
  // block's markup in when a save is answered while the caret is elsewhere (here, in the menu).
  function targetOf(el, adding) {
    var blk = el.closest('.lb-blk'), row = el.closest('[data-row]');
    return { block: blk.dataset.block, add: adding,
             row: row ? Array.prototype.indexOf.call(row.parentNode.querySelectorAll('[data-row]'), row) : -1 };
  }
  function pickNumber(item) {
    var target = numTarget, typed = item.hasAttribute('data-typed');
    closeNum();
    var blk = target && document.querySelector('.lb-blk[data-block="' + target.block + '"]');
    if (!blk) return;
    var rows = blk.querySelectorAll('.numbers [data-row]'), value, label;
    if (target.add) {
      // The shared builder adds the row (and would have on this click, had we not opened the menu).
      var add = blk.querySelector('[data-row-add]');
      if (!add) return;
      numPass = true;
      add.click();
      numPass = false;
      rows = blk.querySelectorAll('.numbers [data-row]');
      value = rows.length ? rows[rows.length - 1].querySelector('[data-row-field="value"]') : null;
      if (!value || typed) return;                              // a typed number: the new row has the caret
    } else {
      value = rows[target.row] && rows[target.row].querySelector('[data-row-field="value"]');
      if (!value) return;
    }
    label = value.closest('[data-row]').querySelector('[data-row-field="label"]');
    if (typed) {
      value.removeAttribute('data-raw');
      value.removeAttribute('data-live');
      value.removeAttribute('title');
      value.textContent = '';
      value.focus();
      value.dispatchEvent(new Event('input', { bubbles: true }));
      return;
    }
    setLive(value, item);
    if (label && isStockLabel(label.textContent)) label.textContent = item.dataset.label;
    if (document.activeElement === value) value.blur();
    saveRow(label || value);
  }

  if (numMenu) {
    document.addEventListener('click', function (e) {
      var item = e.target.closest('#rb-num-menu .rb-num-item');
      if (item) { pickNumber(item); return; }
      var add = !numPass && e.target.closest('[data-row-add]');
      if (add && add.closest('.lb-blk') && add.closest('.lb-blk').querySelector('[data-rows="numbers"]')) {
        e.preventDefault();
        e.stopPropagation();
        openNum(add, targetOf(add, true));
        return;
      }
      var live = e.target.closest(LIVE);
      if (live) { openNum(live, targetOf(live, false)); return; }
      if (!e.target.closest('#rb-num-menu')) closeNum();
    }, true);
    // A live number takes no caret: the mouse opens the menu, the keyboard does with Enter.
    document.addEventListener('mousedown', function (e) {
      if (e.target.closest && e.target.closest(LIVE)) e.preventDefault();
    }, true);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !numMenu.hidden) { closeNum(); return; }
      var live = e.target.closest && e.target.closest(LIVE);
      if (!live || e.key === 'Tab') return;
      e.preventDefault();
      if (e.key === 'Enter' || e.key === ' ') openNum(live, targetOf(live, false));
    }, true);
    document.addEventListener('beforeinput', function (e) {
      if (e.target.closest && e.target.closest(LIVE)) e.preventDefault();
    }, true);
    window.addEventListener('resize', closeNum);
    document.addEventListener('scroll', function (e) { if (e.target !== numMenu) closeNum(); }, true);
  }

  /* ─── the address is applied when the field is left, never while typing ── */
  var slug = document.getElementById('rb-slug');
  if (slug) slug.addEventListener('input', function (e) { e.stopPropagation(); });

  /* ─── library: another survey's charts and maps (change report-home-survey) ── */
  document.addEventListener('change', function (e) {
    var t = e.target;
    if (t.matches('[data-rb-submit]')) { t.form.submit(); return; }
    if (t.id !== 'rb-lib-source') return;
    var groups = document.getElementById('rb-lib-groups'), search = document.getElementById('lb-lib-search');
    groups.classList.add('rb-busy');
    fetch(t.dataset.url + '?source=' + encodeURIComponent(t.value), {credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}})
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        // Our own template, rendered by the `library` route.
        var doc = new DOMParser().parseFromString(html, 'text/html');
        groups.replaceChildren.apply(groups, Array.prototype.slice.call(doc.body.childNodes));
        // The search box keeps what was typed: filter the new tiles by it.
        if (search) search.dispatchEvent(new Event('input'));
      })
      .catch(function () { /* the tiles of the survey shown before stay */ })
      .then(function () { groups.classList.remove('rb-busy'); });
  });

  /* ─── publish: the dialog loads the checks, its form posts the choices ── */
  function openPublish() {
    if (!window.jQuery || !window.htmx) return;
    window.jQuery('#prPublishModal').modal('show');
    window.htmx.ajax('GET', root.dataset.checksUrl, { target: '#prPublishBody', swap: 'innerHTML' });
  }
  function setPublished(publish) {
    var data = new FormData();
    data.append('publish', publish ? '1' : '0');
    return fetch(root.dataset.publishUrl, { method: 'POST', headers: headers(), body: data, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw r; return r.json(); })
      .then(function () { window.location.reload(); });
  }
  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-rb-publish]')) { openPublish(); return; }
    var off = e.target.closest('[data-rb-unpublish]');
    if (off) {
      off.disabled = true;
      setPublished(false).catch(function () {
        off.disabled = false;
        off.textContent = T.unpublishFailed;
      });
    }
  });
  // Called by the dialog's form (editor/partials/pr_checks.html).
  window.prOpenPublish = openPublish;
  window.prSubmitPublish = function (form) {
    var msg = form.querySelector('[data-pr-publish-error]');
    fetch(form.action, { method: 'POST', headers: headers(), body: new FormData(form), credentials: 'same-origin' })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (result) {
        if (result.ok) { window.location.reload(); return; }
        if (msg) {
          msg.hidden = false;
          msg.textContent = result.data.error === 'ack_required' ? T.ack : T.notPublished;
        }
      });
    return false;
  };
  window.prCheckDelete = function (button) {
    fetch(button.dataset.url, { method: 'POST', headers: { 'X-CSRFToken': csrf(), 'HX-Request': 'true' }, credentials: 'same-origin' })
      .then(function () {
        // The block is gone from the report: take it off the canvas too, then check again.
        var id = (button.dataset.url.match(/blocks\/(\d+)\//) || [])[1];
        if (id) {
          document.querySelectorAll('.lb-item[data-block="' + id + '"], .lb-oi[data-block="' + id + '"], .lb-pane[data-pane="' + id + '"]')
            .forEach(function (el) { el.remove(); });
        }
        openPublish();
      });
  };

  /* ─── PDF and the charts-and-maps archive: ask, poll, open ───────────── */
  document.addEventListener('click', function (e) {
    var button = e.target.closest('[data-rb-pdf]');
    if (!button) return;
    var status = document.getElementById('prPdfStatus');
    var url = button.dataset.url, kind = button.dataset.rbPdf;
    var form = new FormData();
    form.append('kind', kind);
    button.disabled = true;
    status.textContent = T.making;
    function done(text) { button.disabled = false; status.textContent = text; }
    function poll(job) {
      fetch(url + '?job=' + job, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status === 'done') {
            done('');
            if (kind === 'zip') window.location = data.url; else window.open(data.url, '_blank');
          } else if (data.status === 'failed') {
            done(T.pdfFailed);
          } else {
            setTimeout(function () { poll(job); }, 2000);
          }
        }).catch(function () { done(T.pdfFailed); });
    }
    fetch(url, { method: 'POST', headers: headers(), body: form, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) { poll(data.job); })
      .catch(function () { done(T.pdfFailed); });
  });

  /* ─── phone / computer width: the interest signal the preview pane sent ─ */
  document.querySelectorAll('#lb-device button').forEach(function (b) {
    b.addEventListener('click', function () {
      if (window.posthog) {
        try { window.posthog.capture('report_previewed', { device: b.dataset.width === 'mobile' ? 'phone' : 'desktop' }); } catch (e) { /* analytics never breaks the page */ }
      }
    });
  });

  /* ─── quotes picked from the answers (change report-quotes-from-answers, #749) ──────────────
   * The Quotes block's pane has a picker card ([data-quote-picker]) outside its form. It is filled
   * from the `quotes` route when the pane is shown, and again whenever the builder swaps the pane in
   * after a save — with what the author last chose, kept here per block. "Add" makes a row through
   * the shared builder's own "Write a quote" button and fills it, so the row saves like a typed one,
   * with `data-ref` telling the server where it came from. ───────────────────────────────────── */
  var lbPanel = document.getElementById('lb-panel');
  var pickState = {}, pickTimer = null;

  function pickerBody(id) {
    return lbPanel.querySelector('[data-quote-picker="' + id + '"] [data-qpick-body]');
  }
  function loadPicker(card, focusSearch) {
    var id = card.dataset.quotePicker, state = pickState[id] || {};
    var params = new URLSearchParams();
    if (state.source) params.set('source', state.source);
    if (state.question) params.set('question', state.question);
    if (state.q) params.set('q', state.q);
    card.dataset.loaded = '1';
    card.querySelector('[data-qpick-body]').classList.add('rb-busy');
    fetch(card.dataset.url + '?' + params.toString(), { headers: headers(), credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        var live = pickerBody(id);
        if (!live) return;
        // Our own template, rendered by the `quotes` route.
        var doc = new DOMParser().parseFromString(html, 'text/html');
        live.replaceChildren.apply(live, Array.prototype.slice.call(doc.body.childNodes));
        if (focusSearch) {
          var s = live.querySelector('[data-qpick-search]');
          if (s) { s.focus(); s.setSelectionRange(s.value.length, s.value.length); }
        }
      })
      .catch(function () { var live = pickerBody(id); if (live) live.textContent = T.quotesFailed || ''; })
      .then(function () { var live = pickerBody(id); if (live) live.classList.remove('rb-busy'); });
  }
  function loadVisiblePickers() {
    lbPanel.querySelectorAll('[data-quote-picker]').forEach(function (card) {
      var pane = card.closest('.lb-pane');
      if (!card.dataset.loaded && pane && !pane.hidden) loadPicker(card, false);
    });
  }
  function readPicker(card) {
    var id = card.dataset.quotePicker, state = pickState[id] = pickState[id] || {};
    var src = card.querySelector('[data-qpick-source]'), q = card.querySelector('[data-qpick-question]');
    var s = card.querySelector('[data-qpick-search]');
    state.source = src ? src.value : state.source;
    state.question = q ? q.value : '';
    state.q = s ? s.value : '';
    return state;
  }
  function addQuote(button) {
    var card = button.closest('[data-quote-picker]'), list = button.closest('.rb-qpick-list');
    var li = button.closest('li'), id = card.dataset.quotePicker;
    var blk = document.querySelector('.lb-blk[data-block="' + id + '"]');
    var write = blk && blk.querySelector('[data-row-add]');
    if (!write) return;
    write.click();                                      // the shared builder adds the row
    var rows = blk.querySelectorAll('.quotes [data-row]'), row = rows[rows.length - 1];
    if (!row) return;
    row.setAttribute('data-ref', list.dataset.ref);
    var text = row.querySelector('[data-row-field="text"]'), source = row.querySelector('[data-row-field="source"]');
    text.textContent = li.querySelector('.rb-qpick-text').textContent;
    if (source) source.textContent = list.dataset.source;
    if (document.activeElement && row.contains(document.activeElement)) document.activeElement.blur();
    text.dispatchEvent(new Event('input', { bubbles: true }));   // queues the block's autosave
    text.dispatchEvent(new Event('blur'));                       // and sends it now
    li.classList.add('is-taken');
    var added = document.createElement('span');
    added.className = 'rb-qpick-added';
    added.textContent = T.quoteAdded || '✓';
    button.replaceWith(added);
  }

  if (lbPanel) {
    new MutationObserver(loadVisiblePickers).observe(lbPanel, { subtree: true, childList: true, attributes: true, attributeFilter: ['hidden'] });
    loadVisiblePickers();
    lbPanel.addEventListener('change', function (e) {
      var card = e.target.closest('[data-quote-picker]');
      if (!card || !e.target.matches('[data-qpick-source], [data-qpick-question]')) return;
      var state = readPicker(card);
      if (e.target.matches('[data-qpick-source]')) state.question = '';
      state.q = '';
      loadPicker(card, false);
    });
    lbPanel.addEventListener('input', function (e) {
      var card = e.target.closest('[data-quote-picker]');
      if (!card || !e.target.matches('[data-qpick-search]')) return;
      readPicker(card);
      clearTimeout(pickTimer);
      pickTimer = setTimeout(function () { loadPicker(card, true); }, 300);
    });
    lbPanel.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && e.target.matches && e.target.matches('[data-qpick-search]')) e.preventDefault();
    });
    lbPanel.addEventListener('click', function (e) {
      var add = e.target.closest('[data-qpick-add]');
      if (add) addQuote(add);
    });
  }
  // "Pick from answers" on the canvas selects the block (data-select-target); then the picker.
  document.addEventListener('click', function (e) {
    var pick = e.target.closest('[data-quote-pick]');
    if (!pick || !lbPanel) return;
    var id = pick.closest('.lb-blk').dataset.block;
    setTimeout(function () {
      var card = lbPanel.querySelector('[data-quote-picker="' + id + '"]');
      if (!card) return;
      card.scrollIntoView({ block: 'nearest' });
      var s = card.querySelector('[data-qpick-search]') || card.querySelector('[data-qpick-source]');
      if (s) s.focus();
    }, 80);
  });

  // A link from the publish checks or a comment (`?block=<id>`) lands on the block.
  if (frame && root.dataset.selected && root.dataset.selected !== 'page') {
    var target = document.getElementById('block-' + root.dataset.selected);
    if (target) setTimeout(function () { target.scrollIntoView({ block: 'center' }); }, 60);
  }
})();
