/* editor_dialog.js — replaces native window.confirm / window.alert / hx-confirm
 * with a single Bootstrap-styled, centered modal (#editorDialog) defined in
 * editor_base.html.
 *
 * Public surface:
 *   Dialog.confirm(message, opts) -> Promise<boolean>
 *     opts: { title?: string, note?: string, okLabel?: string, danger?: boolean }
 *   A form with data-confirm="<title>" (optional data-confirm-body, -note,
 *   -action, -tone="primary" for an action that destroys nothing) is held on
 *   submit and sent when the dialog is confirmed.
 *   Dialog.alert(message, opts)   -> Promise<void>
 *     opts: { title?: string, okLabel?: string }
 *
 * Behaviour:
 *   - Backdrop click / ESC resolve confirm() with false (cancel) and alert() void.
 *   - If #editorDialog or jQuery is unavailable, falls back to native window
 *     primitives so call sites stay safe even outside the editor base template.
 *   - Auto-installs an htmx:confirm listener that diverts every hx-confirm
 *     prompt through Dialog.confirm with a danger-styled OK button (every
 *     hx-confirm site in the editor today is destructive: delete section /
 *     question, remove collaborator).
 */
(function (window) {
    'use strict';

    var $ = window.jQuery;
    var MODAL_ID = '#editorDialog';

    function _native(message, isConfirm, opts) {
        opts = opts || {};
        message = [opts.title, message, opts.note].filter(Boolean).join('\n\n');
        if (isConfirm) return Promise.resolve(window.confirm(message));
        window.alert(message);
        return Promise.resolve();
    }

    function _show(message, opts, isConfirm) {
        if (!$ || !$(MODAL_ID).length) return _native(message, isConfirm, opts);
        opts = opts || {};

        var modal = $(MODAL_ID);
        // One element serves every dialog. A request issued from a confirm's
        // OK can answer (409 → Dialog.alert) while that confirm is still
        // fading out; Bootstrap ignores show() mid-transition, the alert never
        // appears and its backdrop stays over the page — every button then
        // "does nothing". Queue behind the hide instead.
        var state = modal.data('bs.modal');
        // Bootstrap 4 keeps _isShown until `hidden` fires and refuses show()
        // meanwhile; the class alone drops at the start of the fade.
        if (modal.hasClass('show') || (state && (state._isShown || state._isTransitioning))) {
            return new Promise(function (resolve) {
                modal.one('hidden.bs.modal.editorDialogQueue', function () {
                    _show(message, opts, isConfirm).then(resolve);
                });
            });
        }
        var $title = modal.find('#editorDialogTitle');
        var $msg = modal.find('#editorDialogMessage');
        var $cancel = modal.find('#editorDialogCancel');
        var $ok = modal.find('#editorDialogOk');

        var words = modal[0].dataset;
        $title.text(opts.title || (isConfirm ? words.confirmTitle || 'Confirm' : words.noticeTitle || 'Notice'));
        $msg.text(message || '').prop('hidden', !message);
        modal.find('#editorDialogNote').text(opts.note || '');
        modal.find('#editorDialogNoteRow').prop('hidden', !opts.note);

        if (isConfirm) {
            $cancel.show();
        } else {
            $cancel.hide();
        }

        $ok.text(opts.okLabel || words.ok || 'OK')
            .removeClass('btn-primary btn-danger btn-warning btn-success')
            .addClass(opts.danger ? 'btn-danger' : 'btn-primary');

        return new Promise(function (resolve) {
            var resolved = false;
            function settle(value) {
                if (resolved) return;
                resolved = true;
                $ok.off('click.editorDialog');
                modal.off('hidden.bs.modal.editorDialog');
                resolve(value);
            }
            $ok.on('click.editorDialog', function () {
                settle(isConfirm ? true : undefined);
                modal.modal('hide');
            });
            modal.on('hidden.bs.modal.editorDialog', function () {
                settle(isConfirm ? false : undefined);
            });
            modal.modal('show');
        });
    }

    var Dialog = {
        confirm: function (message, opts) { return _show(message, opts, true); },
        alert: function (message, opts) { return _show(message, opts, false); },
    };

    // ─── htmx:confirm hook ──────────────────────────────────────────────────
    // htmx fires this event before issuing any request that has hx-confirm set.
    // Default handler calls window.confirm(); we replace it with Dialog.confirm
    // and call detail.issueRequest(true) on OK (the `true` flag tells htmx to
    // skip its own confirm step and avoid a second prompt).
    document.addEventListener('htmx:confirm', function (evt) {
        if (!evt.detail || !evt.detail.question) return;
        evt.preventDefault();
        Dialog.confirm(evt.detail.question, {
            title: 'Confirm',
            okLabel: (document.querySelector(MODAL_ID) || {dataset: {}}).dataset.delete || 'Delete',
            danger: true,
        }).then(function (ok) {
            if (ok && typeof evt.detail.issueRequest === 'function') {
                evt.detail.issueRequest(true);
            }
        });
    });

    // ─── forms that ask first ───────────────────────────────────────────────
    // <form data-confirm="Delete “X”?" data-confirm-body="…" data-confirm-note="…"
    //       data-confirm-action="Delete report">: texts go in with textContent.
    document.addEventListener('submit', function (evt) {
        var form = evt.target && evt.target.closest ? evt.target.closest('form[data-confirm]') : null;
        if (!form || form.dataset.confirmed === '1') return;
        evt.preventDefault();
        evt.stopImmediatePropagation();
        var submitter = evt.submitter;
        var d = form.dataset;
        var words = (document.querySelector(MODAL_ID) || {dataset: {}}).dataset;
        var primary = d.confirmTone === 'primary';
        Dialog.confirm(d.confirmBody || '', {
            title: d.confirm,
            note: d.confirmNote || '',
            okLabel: d.confirmAction || (primary ? words.ok : words.delete) || 'OK',
            danger: !primary,
        }).then(function (ok) {
            if (!ok) return;
            form.dataset.confirmed = '1';
            if (submitter && submitter.name) {
                var carry = document.createElement('input');
                carry.type = 'hidden';
                carry.name = submitter.name;
                carry.value = submitter.value;
                form.appendChild(carry);
            }
            form.submit();
        });
    }, true);

    window.Dialog = Dialog;
})(window);
