/* "Other, please specify" write-in (openspec: other-option-write-in).
 *
 * The widget renders the input under the flagged option as
 *   <div class="other-writein" data-other-for="<field name>" data-other-code="<code>" hidden>
 *     <input name="<field name>-other" disabled>
 *   </div>
 * This module only decides whether it shows: the flagged option is selected in
 * the closest form. Hidden means disabled too -- a disabled input never posts,
 * and the required-question check counts any non-empty input as "filled", so
 * a stale write-in must not make an unanswered card pass. Pure name/value
 * matching, never ids: popup forms are clones of one HTML string. Popups
 * restore values without events, so their open handlers call
 * window.syncOtherWriteins(popupElement) themselves.
 */
(function () {
    'use strict';

    function selectedValues(form, name) {
        var values = [];
        form.querySelectorAll('[name="' + name + '"]').forEach(function (el) {
            var type = (el.type || '').toLowerCase();
            if (type === 'radio' || type === 'checkbox') {
                if (el.checked) values.push(String(el.value));
            } else if (el.tagName.toLowerCase() === 'select') {
                Array.prototype.forEach.call(el.selectedOptions || [], function (o) {
                    values.push(String(o.value));
                });
            }
        });
        return values;
    }

    function sync(root, focusRevealed) {
        if (!root || !root.querySelectorAll) return;
        root.querySelectorAll('.other-writein[data-other-for]').forEach(function (wrap) {
            var form = wrap.closest('form') || root;
            var show = selectedValues(form, wrap.getAttribute('data-other-for'))
                .indexOf(String(wrap.getAttribute('data-other-code'))) !== -1;
            var input = wrap.querySelector('input');
            var wasHidden = wrap.hidden;
            wrap.hidden = !show;
            if (input) {
                input.disabled = !show;
                if (show && wasHidden && focusRevealed) input.focus();
            }
        });
    }

    // Runs after conditional_visibility.js on the same event (it is loaded
    // first), so a card it just re-enabled gets its hidden write-in disabled
    // again here.
    document.addEventListener('change', function (e) {
        var form = e.target && e.target.closest ? e.target.closest('form') : null;
        if (form) sync(form, true);
    });
    function syncAll() { sync(document, false); }
    document.addEventListener('DOMContentLoaded', syncAll);
    document.addEventListener('htmx:afterSwap', syncAll);
    window.syncOtherWriteins = sync;
})();
