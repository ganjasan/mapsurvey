/* Comments drawer chrome (spec survey-comment-threads).
 *
 * The drawer shell lives once in editor_base.html; the panel inside it is a
 * server partial loaded over HTMX. This file only does what the server cannot:
 * open/close with focus management, the #thread-<id> deep link, Esc ordering
 * above a Bootstrap modal, refreshing every badge after an action, inline error
 * display, client-side file checks, the @mention picker and the resize handle.
 * Everything it puts on the page is built with DOM calls and textContent —
 * member names and file names never go through markup.
 */
(function () {
  'use strict';

  var drawer = null;
  var opener = null;          // element that opened the drawer, gets focus back on close
  var MAX_FILE = 15 * 1024 * 1024;

  function el() {
    if (!drawer) drawer = document.getElementById('comments-drawer');
    return drawer;
  }

  function body() { return document.getElementById('comments-drawer-body'); }

  function make(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function announce(text) {
    var d = el();
    var live = d && d.querySelector('[data-cm-live]');
    if (!live) return;
    live.textContent = '';
    setTimeout(function () { live.textContent = text; }, 30);
  }

  function load(params) {
    var d = el();
    if (!d || !window.htmx) return null;
    var url = d.dataset.panelUrl;
    var qs = [];
    if (params) Object.keys(params).forEach(function (k) {
      if (params[k] !== undefined && params[k] !== null && params[k] !== '') qs.push(k + '=' + encodeURIComponent(params[k]));
    });
    if (qs.length) url += '?' + qs.join('&');
    return htmx.ajax('GET', url, { target: '#comments-drawer-body', swap: 'innerHTML' });
  }

  // ---- resize ---------------------------------------------------------------
  var WIDTH_KEY = 'cmDrawerWidth';
  var MIN_W = 320;

  function maxWidth() { return Math.max(MIN_W, Math.floor(window.innerWidth * 0.8)); }

  function setWidth(d, w, persist) {
    w = Math.min(maxWidth(), Math.max(MIN_W, w | 0));
    d.style.width = w + 'px';
    var h = d.querySelector('[data-cm-resize]');
    if (h) { h.setAttribute('aria-valuenow', String(w)); h.setAttribute('aria-valuemax', String(maxWidth())); }
    if (persist) { try { localStorage.setItem(WIDTH_KEY, String(w)); } catch (e) { /* storage blocked */ } }
  }

  function applyStoredWidth(d) {
    var w = null;
    try { w = parseInt(localStorage.getItem(WIDTH_KEY), 10); } catch (e) { /* storage blocked */ }
    if (w && w >= MIN_W) setWidth(d, w, false);
  }

  function bindResize(d) {
    var h = d.querySelector('[data-cm-resize]');
    if (!h || h.dataset.cmBound) return;
    h.dataset.cmBound = '1';
    var startX = 0, startW = 0;
    function move(e) { setWidth(d, startW + (startX - e.clientX), false); }
    function up() {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', up);
      d.classList.remove('cm-resizing');
      document.body.classList.remove('cm-resizing-body');
      setWidth(d, d.getBoundingClientRect().width, true);
    }
    h.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      startX = e.clientX;
      startW = d.getBoundingClientRect().width;
      d.classList.add('cm-resizing');
      document.body.classList.add('cm-resizing-body');
      document.addEventListener('pointermove', move);
      document.addEventListener('pointerup', up);
    });
    h.addEventListener('dblclick', function () {
      d.style.width = '';
      h.setAttribute('aria-valuenow', '420');
      try { localStorage.removeItem(WIDTH_KEY); } catch (e) { /* ignore */ }
    });
    h.addEventListener('keydown', function (e) {
      var w = d.getBoundingClientRect().width;
      if (e.key === 'ArrowLeft') setWidth(d, w + 40, true);
      else if (e.key === 'ArrowRight') setWidth(d, w - 40, true);
      else return;
      e.preventDefault();
    });
  }

  // ---- open / close with focus management ------------------------------------
  function open(params, from) {
    var d = el();
    if (!d) return;
    opener = from || (document.activeElement && document.activeElement !== document.body ? document.activeElement : null);
    bindResize(d);
    applyStoredWidth(d);
    d.classList.add('open');
    d.setAttribute('aria-hidden', 'false');
    document.body.classList.add('cm-drawer-open');
    var p = load(params);
    if (p && p.then) p.then(function () { focusThread(); focusTitle(); });
  }

  function focusTitle() {
    var b = body();
    var panel = b && b.querySelector('[data-cm-panel]');
    if (panel && panel.dataset.focusThread) return;   // the deep link scrolls to the thread instead
    var t = b && b.querySelector('[data-cm-title]');
    if (t) t.focus({ preventScroll: true });
  }

  function close() {
    var d = el();
    if (!d) return;
    d.classList.remove('open');
    d.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('cm-drawer-open');
    if (opener && document.contains(opener) && typeof opener.focus === 'function') opener.focus();
    opener = null;
  }

  function isOpen() { var d = el(); return !!(d && d.classList.contains('open')); }

  function focusThread() {
    var b = body();
    var panel = b && b.querySelector('[data-cm-panel]');
    if (!panel) return;
    var id = panel.dataset.focusThread;
    if (!id) return;
    var t = document.getElementById('thread-' + id);
    if (t) { t.scrollIntoView({ block: 'center', behavior: 'smooth' }); t.setAttribute('tabindex', '-1'); t.focus({ preventScroll: true }); }
  }

  // ---- badges ---------------------------------------------------------------
  function refreshBadges() {
    var d = el();
    if (!d) return;
    fetch(d.dataset.countsUrl, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        var fresh = data.new || [];
        document.querySelectorAll('[data-thread-badge]').forEach(function (b) {
          var key = b.dataset.threadBadge;
          var n = data.counts[key] || 0;
          var isNew = fresh.indexOf(key) !== -1;
          if (b.classList.contains('cm-badge')) {
            b.classList.toggle('cm-ghost', n === 0);
            b.classList.toggle('cm-badge--new', isNew);
          }
          var num = b.querySelector('[data-cm-n]');
          if (num) num.textContent = n || '';
          var label = n ? n + ' open comment' + (n > 1 ? 's' : '') + (isNew ? ', new activity' : '') : 'Add a comment';
          b.title = label;
          if (b.classList.contains('cm-badge')) b.setAttribute('aria-label', label);
        });
        document.querySelectorAll('[data-thread-total]').forEach(function (t) {
          t.textContent = data.total;
          t.hidden = !data.total;
          var btn = t.closest('.cm-toolbar-btn');
          if (btn) btn.classList.toggle('cm-has-new', (data.new_total || 0) > 0);
        });
      })
      .catch(function () {});
  }

  // ---- deep link ------------------------------------------------------------
  function scrollToInline(id, tries) {
    var t = document.getElementById('thread-' + id);
    if (t) { t.classList.add('cm-focus'); t.scrollIntoView({ block: 'center', behavior: 'smooth' }); return; }
    if (tries > 0) setTimeout(function () { scrollToInline(id, tries - 1); }, 250);
  }

  function openFromHash() {
    var hash = window.location.hash || '';
    if (hash === '#comments') {
      // The dashboard badge lands here: the whole survey's threads, new ones first.
      setTimeout(function () { open({}); }, 150);
      return;
    }
    var m = hash.match(/^#thread-(\d+)$/);
    if (!m) return;
    var sessionId = (window.location.search.match(/[?&]session=(\d+)/) || [])[1];
    if (sessionId && typeof window.loadSessionDetail === 'function') {
      setTimeout(function () { window.loadSessionDetail(parseInt(sessionId, 10)); scrollToInline(m[1], 16); }, 300);
      return;
    }
    setTimeout(function () { open({ thread: m[1] }); }, 150);
  }

  // ---- composer: mentions, files, errors -------------------------------------
  function membersFor(form) {
    var scope = form.closest('[data-cm-panel]') || document;
    var s = scope.querySelector('script[type="application/json"][id^="cm-members"]');
    if (!s) return [];
    try { return JSON.parse(s.textContent); } catch (e) { return []; }
  }

  function showError(form, text) {
    var box = form.querySelector('[data-cm-error]');
    if (!box) { window.alert(text); return; }
    box.textContent = text;
    box.hidden = false;
  }

  function clearError(form) {
    var box = form.querySelector('[data-cm-error]');
    if (box) { box.hidden = true; box.textContent = ''; }
  }

  function renderPending(form, files) {
    var pending = form.querySelector('[data-cm-pending]');
    var input = form.querySelector('[data-cm-files]');
    if (!pending || !input) return;
    while (pending.firstChild) pending.removeChild(pending.firstChild);
    var kept = [];
    var problems = [];
    Array.prototype.forEach.call(files, function (f) {
      var bad = f.size > MAX_FILE ? 'over 15 MB' : '';
      var chip = make('span', 'cm-pending-chip' + (bad ? ' cm-bad' : ''));
      chip.appendChild(make('i', 'fas fa-paperclip'));
      chip.appendChild(make('span', '', ' ' + f.name + ' '));
      chip.appendChild(make('small', '', (f.size / 1048576).toFixed(1) + ' MB' + (bad ? ' · ' + bad : '')));
      var x = make('button', '', '×');
      x.type = 'button';
      x.setAttribute('aria-label', 'Remove ' + f.name);
      x.addEventListener('click', function () {
        renderPending(form, kept.filter(function (k) { return k !== f; }));
      });
      chip.appendChild(x);
      pending.appendChild(chip);
      if (bad) problems.push(f.name + ' is ' + bad + '.'); else kept.push(f);
    });
    // Rebuild the input's file list without the removed/oversized ones.
    try {
      var dt = new DataTransfer();
      kept.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
    } catch (e) { /* older browsers keep the original selection */ }
    pending.hidden = pending.childElementCount === 0;
    if (problems.length) showError(form, problems.join(' ') + ' Files can be at most 15 MB.'); else clearError(form);
  }

  function bindComposer(form) {
    if (form.dataset.cmBound) return;
    form.dataset.cmBound = '1';
    var ta = form.querySelector('[data-cm-body]') || form.querySelector('textarea');
    var list = form.querySelector('[data-cm-mentions]');
    var inputs = form.querySelector('[data-cm-mention-inputs]');
    var files = form.querySelector('[data-cm-files]');
    if (!ta) return;
    var all = list ? membersFor(form) : [];

    function showList(filter) {
      if (!list) return;
      var q = (filter || '').toLowerCase();
      var hits = all.filter(function (m) { return !q || m.name.toLowerCase().indexOf(q) !== -1; }).slice(0, 8);
      while (list.firstChild) list.removeChild(list.firstChild);
      hits.forEach(function (m) {
        var row = make('div', 'cm-mention-row');
        row.setAttribute('role', 'option');
        row.appendChild(make('span', 'cm-av', (m.name.charAt(0) || '?').toUpperCase()));
        row.appendChild(make('span', '', m.name));
        row.appendChild(make('small', '', m.email || ''));
        row.addEventListener('mousedown', function (e) { e.preventDefault(); pick(m); });
        list.appendChild(row);
      });
      list.hidden = hits.length === 0;
    }

    function pick(m) {
      var v = ta.value;
      var at = v.lastIndexOf('@');
      ta.value = (at >= 0 ? v.slice(0, at) : v + ' ') + '@' + m.name + ' ';
      if (inputs) {
        var exists = Array.prototype.some.call(inputs.querySelectorAll('input'), function (i) { return i.value === String(m.id); });
        if (!exists) {
          var inp = document.createElement('input');
          inp.type = 'hidden'; inp.name = 'mentions'; inp.value = String(m.id);
          inputs.appendChild(inp);
        }
      }
      if (list) list.hidden = true;
      ta.focus();
    }

    ta.addEventListener('input', function () {
      clearError(form);
      if (!list) return;
      var v = ta.value;
      var at = v.lastIndexOf('@');
      if (at === -1 || (at > 0 && !/\s/.test(v.charAt(at - 1)))) { list.hidden = true; return; }
      var tail = v.slice(at + 1);
      if (/\s/.test(tail)) { list.hidden = true; return; }
      showList(tail);
    });
    ta.addEventListener('blur', function () { if (list) setTimeout(function () { list.hidden = true; }, 120); });
    ta.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && list && !list.hidden) { list.hidden = true; e.stopPropagation(); return; }
      if (e.key === 'Enter' && list && !list.hidden && list.firstChild) {
        e.preventDefault();
        var first = all.filter(function (m) { return list.firstChild && list.firstChild.children[1].textContent === m.name; })[0];
        if (first) pick(first);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); if (form.requestSubmit) form.requestSubmit(); }
    });
    var atBtn = form.querySelector('[data-cm-at]');
    if (atBtn) atBtn.addEventListener('click', function () {
      if (!/(^|\s)@$/.test(ta.value)) ta.value += (ta.value && !/\s$/.test(ta.value) ? ' ' : '') + '@';
      ta.focus(); showList('');
    });
    if (files) files.addEventListener('change', function () { renderPending(form, Array.prototype.slice.call(files.files)); });
  }

  function bindAll(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('[data-cm-composer], [data-cm-editform]').forEach(bindComposer);
  }

  // ---- events ---------------------------------------------------------------
  document.addEventListener('click', function (e) {
    var sb = e.target.closest('[data-cm-session]');
    if (sb) {
      var tries = 16;
      (function wait() {
        var p = document.querySelector('#rv2-drawer-body [data-cm-panel], #sessionDetailModal.show [data-cm-panel]');
        if (p) { p.scrollIntoView({ block: 'start', behavior: 'smooth' }); return; }
        if (tries-- > 0) setTimeout(wait, 250);
      })();
      return;
    }
    var t = e.target.closest('[data-cm-open]');
    if (t) {
      e.preventDefault();
      var anchor = t.getAttribute('data-cm-open');
      open(anchor ? { anchor: anchor } : {}, t);
      return;
    }
    if (e.target.closest('[data-cm-close]')) { e.preventDefault(); close(); return; }
    var r = e.target.closest('[data-cm-reply-toggle]');
    if (r) {
      var thread = r.closest('.cm-thread');
      var form = thread && thread.querySelector('form.cm-reply');
      if (form) {
        form.hidden = !form.hidden;
        r.setAttribute('aria-expanded', form.hidden ? 'false' : 'true');
        if (!form.hidden) { bindComposer(form); var ta = form.querySelector('[data-cm-body]'); if (ta) ta.focus(); }
      }
      return;
    }
    var ed = e.target.closest('[data-cm-edit-toggle]');
    if (ed) {
      var msg = ed.closest('.cm-msg');
      var ef = msg && msg.querySelector('[data-cm-editform]');
      var txt = msg && msg.querySelector('[data-cm-body-text]');
      if (ef) { ef.hidden = false; if (txt) txt.hidden = true; bindComposer(ef); ef.querySelector('textarea').focus(); }
      return;
    }
    var cancel = e.target.closest('[data-cm-edit-cancel]');
    if (cancel) {
      var ef2 = cancel.closest('[data-cm-editform]');
      var msg2 = cancel.closest('.cm-msg');
      var txt2 = msg2 && msg2.querySelector('[data-cm-body-text]');
      if (ef2) { ef2.hidden = true; ef2.querySelector('textarea').value = ef2.querySelector('textarea').defaultValue; }
      if (txt2) txt2.hidden = false;
      return;
    }
  });

  // Session-row badges are spans inside the row button; make them keyboard-operable.
  document.addEventListener('keydown', function (e) {
    var sb = e.target.closest && e.target.closest('[data-cm-session]');
    if (sb && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); sb.click(); }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen()) {
      // The drawer sits above the question modal: Esc closes the drawer first
      // and must not reach Bootstrap's modal handler.
      e.stopImmediatePropagation();
      e.preventDefault();
      close();
    }
  }, true);

  document.addEventListener('threadCountsChanged', refreshBadges);
  document.addEventListener('cmAnnounce', function (e) { if (e.detail && e.detail.text) announce(e.detail.text); });
  document.addEventListener('htmx:afterSwap', function (e) {
    if (!e.detail || !e.detail.target) return;
    bindAll(e.detail.target);
    if (e.detail.target.id === 'comments-drawer-body') focusThread();
  });
  document.addEventListener('htmx:responseError', function (e) {
    var x = e.detail && e.detail.xhr;
    var elt = e.detail && e.detail.elt;
    if (!x || !elt || !elt.matches) return;
    var form = elt.matches('form') ? elt : elt.closest('form');
    if (!form || !(form.matches('[data-cm-composer]') || form.matches('[data-cm-editform]'))) return;
    var text = x.status === 400 ? x.responseText : (x.status === 403 ? 'You cannot do that here.' : 'Something went wrong. Try again.');
    showError(form, text);
    announce(text);
  });

  document.addEventListener('DOMContentLoaded', function () {
    bindAll(document);
    openFromHash();
  });
  window.addEventListener('hashchange', openFromHash);

  window.CommentsDrawer = { open: open, close: close, refreshBadges: refreshBadges, load: load };
})();
