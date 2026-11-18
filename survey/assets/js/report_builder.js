/* What the report builder adds to the canvas builder (change reports-canvas-editor, #731).
 *
 * reports/builder.html runs on js/site_builder.js — selection, writing in place, rows, drops,
 * autosave, order, the library, the device toggle are that script's. This one holds what only a
 * report has: the publish dialog with its checks, unpublish, the PDF / ZIP job, half-width blocks
 * sitting side by side, the library's two small forms, and an address that is not saved while it is
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

  /* ─── library: a tile that needs two choices opens its form ──────────── */
  document.addEventListener('click', function (e) {
    var tile = e.target.closest('[data-lib-form]');
    if (!tile) return;
    var body = document.querySelector('[data-lib-form-body="' + tile.dataset.libForm + '"]');
    if (!body) return;
    body.hidden = !body.hidden;
    tile.setAttribute('aria-expanded', body.hidden ? 'false' : 'true');
    if (!body.hidden) { var first = body.querySelector('select'); if (first) first.focus(); }
  });

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

  // A link from the publish checks or a comment (`?block=<id>`) lands on the block.
  if (frame && root.dataset.selected && root.dataset.selected !== 'page') {
    var target = document.getElementById('block-' + root.dataset.selected);
    if (target) setTimeout(function () { target.scrollIntoView({ block: 'center' }); }, 60);
  }
})();
