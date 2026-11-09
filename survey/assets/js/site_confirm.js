/* Confirmation dialog for destructive posts on the sites (sites/editor/_confirm_modal.html).
 * A form with data-confirm="<title>" (and optional data-confirm-body, -note, -action) is held on
 * submit; the dialog shows the texts with textContent and the red button submits the form. */
(function () {
  'use strict';
  var modal = document.getElementById('lb-confirm');
  if (!modal || typeof jQuery === 'undefined') return;
  var pending = null;
  var defaultAction = document.getElementById('lb-confirm-go').textContent;

  document.addEventListener('submit', function (e) {
    var form = e.target.closest('form[data-confirm]');
    if (!form || form.dataset.confirmed === '1') return;
    e.preventDefault();
    e.stopImmediatePropagation();
    pending = form;
    document.getElementById('lb-confirm-title').textContent = form.dataset.confirm;
    var body = document.getElementById('lb-confirm-body');
    body.textContent = form.dataset.confirmBody || '';
    body.hidden = !form.dataset.confirmBody;
    var note = document.getElementById('lb-confirm-note');
    note.textContent = form.dataset.confirmNote || '';
    note.parentNode.hidden = !form.dataset.confirmNote;
    document.getElementById('lb-confirm-go').textContent = form.dataset.confirmAction || defaultAction;
    jQuery(modal).modal('show');
  }, true);

  document.getElementById('lb-confirm-go').addEventListener('click', function () {
    if (!pending) return;
    var form = pending;
    pending = null;
    form.dataset.confirmed = '1';
    jQuery(modal).modal('hide');
    form.submit();
  });
  jQuery(modal).on('shown.bs.modal', function () { document.getElementById('lb-confirm-go').focus(); });
})();
