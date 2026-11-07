/* The landing page builder (change landing-core, #576).
 * Open/close a block's form, Quill on every [data-rich] textarea (the textarea stays the value
 * carrier and is filled on submit), repeating rows for FAQ and timeline, drag-to-reorder that
 * posts the full id list as JSON. Everything else is a plain form post. */
(function () {
  'use strict';

  var TOOLBAR = [['bold', 'italic', 'underline'], [{ header: [2, 3, false] }],
    [{ list: 'ordered' }, { list: 'bullet' }], ['link'], ['clean']];

  function csrf() {
    var input = document.querySelector('input[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function mountRich(textarea) {
    if (typeof Quill === 'undefined' || textarea.dataset.mounted) return;
    textarea.dataset.mounted = '1';
    var mount = document.createElement('div');
    mount.className = 'lb-quill';
    textarea.parentNode.insertBefore(mount, textarea.nextSibling);
    var q = new Quill(mount, { theme: 'snow', modules: { toolbar: TOOLBAR } });
    q.setContents(q.clipboard.convert({ html: textarea.value || '' }), 'silent');
    textarea.style.display = 'none';
    textarea._quill = q;
  }

  function syncRich(form) {
    form.querySelectorAll('textarea[data-rich]').forEach(function (t) {
      if (!t._quill) return;
      var html = t._quill.root.innerHTML;
      t.value = html === '<p><br></p>' ? '' : html;
    });
  }

  function renumberPhases(form) {
    form.querySelectorAll('.lb-rows[data-row-kind=timeline] .lb-row').forEach(function (row, i) {
      var radio = row.querySelector('input[name=current]');
      if (radio) radio.value = String(i);
    });
  }

  document.querySelectorAll('.lb-form').forEach(function (form) {
    form.querySelectorAll('textarea[data-rich]').forEach(mountRich);
    form.addEventListener('submit', function () {
      syncRich(form);
      renumberPhases(form);
    });
    var add = form.querySelector('.lb-row-add');
    var tpl = form.querySelector('template.lb-row-template');
    var rows = form.querySelector('.lb-rows');
    if (add && tpl && rows) {
      add.addEventListener('click', function () {
        var node = tpl.content.firstElementChild.cloneNode(true);
        rows.appendChild(node);
        node.querySelectorAll('textarea[data-rich]').forEach(mountRich);
        var first = node.querySelector('input');
        if (first) first.focus();
      });
    }
    form.addEventListener('click', function (e) {
      var btn = e.target.closest('.lb-row-remove');
      if (!btn) return;
      var all = form.querySelectorAll('.lb-rows .lb-row');
      if (all.length > 1) btn.closest('.lb-row').remove();
    });
  });

  document.querySelectorAll('.lb-toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.closest('.lb-block').classList.toggle('lb-open');
    });
  });

  var list = document.getElementById('lb-blocks');
  var root = document.querySelector('.lb[data-reorder-url]');
  if (list && root && list.dataset.sortable && typeof Sortable !== 'undefined') {
    Sortable.create(list, {
      handle: '.lb-handle', animation: 150, delay: 300, delayOnTouchOnly: true,
      onEnd: function () {
        var order = Array.prototype.map.call(list.querySelectorAll(':scope > .lb-block'), function (li) {
          return parseInt(li.dataset.id, 10);
        });
        fetch(root.dataset.reorderUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
          body: JSON.stringify({ order: order })
        }).then(function (r) { if (!r.ok) window.location.reload(); })
          .catch(function () { window.location.reload(); });
      }
    });
  }

  if (window.location.hash === '#new-block') {
    var fresh = document.getElementById('new-block');
    if (fresh) fresh.scrollIntoView({ block: 'center' });
  }
})();
