/* editor_dialog.js — replaces native window.confirm / window.alert / hx-confirm
 * with a single Bootstrap-styled, centered modal (#editorDialog) defined in
 * editor_base.html.
 *
 * Public surface:
 *   Dialog.confirm(message, opts) -> Promise<boolean>
 *     opts: { title?: string, okLabel?: string, danger?: boolean }
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

    function _native(message, isConfirm) {
        if (isConfirm) return Promise.resolve(window.confirm(message));
        window.alert(message);
        return Promise.resolve();
    }

    function _show(message, opts, isConfirm) {
        if (!$ || !$(MODAL_ID).length) return _native(message, isConfirm);
        opts = opts || {};

        var modal = $(MODAL_ID);
        var $title = modal.find('#editorDialogTitle');
        var $msg = modal.find('#editorDialogMessage');
        var $cancel = modal.find('#editorDialogCancel');
        var $ok = modal.find('#editorDialogOk');

        $title.text(opts.title || (isConfirm ? 'Confirm' : 'Notice'));
        $msg.text(message);

        if (isConfirm) {
            $cancel.show();
        } else {
            $cancel.hide();
        }

        $ok.text(opts.okLabel || 'OK')
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
            okLabel: 'Delete',
            danger: true,
        }).then(function (ok) {
            if (ok && typeof evt.detail.issueRequest === 'function') {
                evt.detail.issueRequest(true);
            }
        });
    });

    window.Dialog = Dialog;
})(window);
