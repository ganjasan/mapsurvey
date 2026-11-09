/* Gallery lightbox and before/after slider on public sites (change site-gallery-compare).
 * Progressive: without this script a gallery picture is a link to the file and both before/after
 * pictures show one under the other. */
(function () {
  'use strict';

  // ─── before / after ────────────────────────────────────────────────────
  function initCompare(box) {
    if (box.dataset.ready) return;
    box.dataset.ready = '1';
    var range = box.querySelector('.lp-compare-range');
    var after = box.querySelector('.lp-compare-after');
    if (!range || !after) return;
    box.classList.add('is-live');
    range.hidden = false;
    var set = function () {
      after.style.clipPath = 'inset(0 0 0 ' + range.value + '%)';
      box.style.setProperty('--cut', range.value + '%');
    };
    range.addEventListener('input', set);
    set();
  }

  // ─── lightbox ──────────────────────────────────────────────────────────
  var dialog = null, items = [], at = 0;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function show(i) {
    at = (i + items.length) % items.length;
    var a = items[at], thumb = a.querySelector('img');
    var img = dialog.querySelector('img'), cap = dialog.querySelector('figcaption');
    img.src = a.href;
    img.alt = thumb.alt;
    cap.textContent = thumb.alt;
  }

  function ensureDialog() {
    if (dialog) return dialog;
    dialog = el('dialog', 'lp-lightbox');
    var fig = el('figure');
    fig.appendChild(el('img'));
    fig.appendChild(el('figcaption'));
    dialog.appendChild(fig);
    var prev = el('button', 'lp-lb-prev', '‹'), next = el('button', 'lp-lb-next', '›'), close = el('button', 'lp-lb-close', '×');
    [prev, next, close].forEach(function (b) { b.type = 'button'; b.setAttribute('aria-label', b.textContent); dialog.appendChild(b); });
    document.body.appendChild(dialog);
    prev.addEventListener('click', function () { show(at - 1); });
    next.addEventListener('click', function () { show(at + 1); });
    close.addEventListener('click', function () { dialog.close(); });
    dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') show(at - 1);
      if (e.key === 'ArrowRight') show(at + 1);
    });
    return dialog;
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-gallery] a[data-lightbox]');
    if (!a || typeof HTMLDialogElement === 'undefined' || a.closest('.lb')) return;  // never in the builder
    e.preventDefault();
    items = Array.prototype.slice.call(a.closest('[data-gallery]').querySelectorAll('a[data-lightbox]'));
    ensureDialog();
    show(items.indexOf(a));
    dialog.showModal();
  });

  function init(root) { (root || document).querySelectorAll('[data-compare]').forEach(initCompare); }
  init();
  window.SiteMedia = { init: init };
})();
