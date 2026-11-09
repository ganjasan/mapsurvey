/* Pages of a site in the builder (change site-pages, #628): the page settings form autosaves
 * (autosave=1 → JSON, 422 with field errors) and the rail's page tabs reorder by drag, home first.
 * Selection of the page pane (`sitepage:<id>`) is site_builder.js's own select(). */
(function () {
  'use strict';
  var root = document.getElementById('lb');
  if (!root || root.dataset.mayEdit !== '1') return;
  var T = window.LB_TEXT || {};
  var saved = document.getElementById('lb-saved');

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    var input = document.querySelector('input[name=csrfmiddlewaretoken]');
    return input ? input.value : (m ? decodeURIComponent(m[1]) : '');
  }
  function status(kind) {
    if (!saved) return;
    var icon = saved.querySelector('i'), text = saved.querySelector('span');
    saved.dataset.state = kind;
    icon.className = kind === 'saving' ? 'fas fa-circle-notch fa-spin'
      : kind === 'saved' ? 'fas fa-check-circle' : 'fas fa-exclamation-triangle';
    text.textContent = T[kind] || '';
  }

  // Page settings and update panes (change site-updates): autosave, 422 shows the field errors, the
  // saved title goes to every element that names it (rail tab, canvas card, pane head).
  document.querySelectorAll('form.lb-sitepage-form, form[data-autosave-json]').forEach(function (form) {
    var timer = null, box = form.querySelector('.lb-errors');
    form.querySelectorAll('textarea[data-rich]').forEach(function (t) {
      if (window.LBRich) window.LBRich.bind(t, function () { later(); });
    });
    function flush() {
      timer = null;
      form.querySelectorAll('textarea[data-rich]').forEach(function (t) {
        if (t._host && window.LBRich) t.value = window.LBRich.value(t._host);
      });
      var data = new FormData(form);
      data.append('autosave', '1');
      status('saving');
      fetch(form.action, { method: 'POST', body: data, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf() } })
        .then(function (r) { return r.json().then(function (b) { return { ok: r.ok && b.ok, body: b }; }); })
        .then(function (res) {
          var msgs = res.ok ? [] : Object.keys(res.body.errors || {}).map(function (k) { return res.body.errors[k]; });
          if (box) { box.textContent = msgs.join(' '); box.hidden = !msgs.length; }
          status(res.ok ? 'saved' : 'failed');
          if (!res.ok) return;
          var sel = form.dataset.pageId
            ? '[data-page-tab="' + form.dataset.pageId + '"], [data-page-title="' + form.dataset.pageId + '"]'
            : '[data-label-for="' + form.dataset.label + '"]';
          document.querySelectorAll(sel).forEach(function (el) {
            var a = el.querySelector('a');
            (a || el).textContent = res.body.title;
          });
        })
        .catch(function () { status('offline'); });
    }
    function later() { status('saving'); clearTimeout(timer); timer = setTimeout(flush, 600); }
    form.addEventListener('submit', function (e) { e.preventDefault(); clearTimeout(timer); flush(); });
    form.addEventListener('input', function (e) {
      if (e.target.matches('input[type=text], input[type=url], input:not([type]), textarea')) later();
    });
    form.addEventListener('change', function (e) {
      if (e.target.matches('input[type=checkbox], input[type=date], select')) { clearTimeout(timer); flush(); }
    });
    window.addEventListener('beforeunload', function (e) { if (timer) { e.preventDefault(); e.returnValue = ''; } });
  });

  // *Add news* / *Add "You said, we did"* inside an updates block (change site-updates). Forms inside a
  // block are inert on the canvas, so the button posts a form of its own; the answer is the builder with
  // the new draft selected.
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-add-update]');
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    var f = document.createElement('form');
    f.method = 'post';
    f.action = b.dataset.url;
    [['csrfmiddlewaretoken', csrf()], ['kind', b.dataset.addUpdate], ['page', b.dataset.page || '']].forEach(function (kv) {
      var i = document.createElement('input');
      i.type = 'hidden'; i.name = kv[0]; i.value = kv[1];
      f.appendChild(i);
    });
    document.body.appendChild(f);
    f.submit();
  }, true);

  var list = document.getElementById('lb-pages');
  if (list && typeof Sortable !== 'undefined') {
    Sortable.create(list, {
      draggable: '.lb-pg:not(.lb-pg-home)', handle: '.lb-pg-h', animation: 150, delay: 300, delayOnTouchOnly: true,
      filter: '.lb-pg-home',
      // Nothing goes above home.
      onMove: function (e) { return !e.related.classList.contains('lb-pg-home') || e.willInsertAfter; },
      onEnd: function () {
        var order = Array.prototype.map.call(list.querySelectorAll('.lb-pg:not(.lb-pg-home)'), function (li) {
          return parseInt(li.dataset.page, 10);
        });
        status('saving');
        fetch(root.dataset.pagesReorderUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
          body: JSON.stringify({ order: order })
        }).then(function (r) { status(r.ok ? 'saved' : 'offline'); if (!r.ok) window.location.reload(); })
          .catch(function () { status('offline'); });
      }
    });
  }
})();
