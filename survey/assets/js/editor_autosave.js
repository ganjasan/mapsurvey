/* Autosave for question edit forms (openspec: mobile-adaptive-refactor,
 * editor-autosave). Loaded only when EDITOR_AUTOSAVE is on.
 *
 * Scope: forms editing an EXISTING question (the modal form whose hx-post
 * points at editor_question_edit). New-question forms keep their explicit
 * Create button — autosaving them would manufacture question records while
 * the creator is still deciding on a type.
 *
 * Mechanics: debounced (800ms) POST of the form to its own hx-post URL with
 * an `autosave=1` marker. Success responses carry the refreshed question
 * list item (same contract as the old Apply button); 422 means validation
 * errors — the form is left untouched and the indicator turns into a loud
 * error state with a retry. Silent failure is explicitly a non-goal: the
 * audit's worst respondent finding was a submit that failed with no UI.
 */
(function () {
    'use strict';

    var DEBOUNCE_MS = 800;

    function indicator(form) {
        return form.querySelector('.autosave-indicator');
    }

    function setState(form, state, message) {
        var el = indicator(form);
        if (!el) return;
        el.setAttribute('data-state', state);
        var label = el.querySelector('.autosave-label');
        if (label) label.textContent = message;
    }

    function serialize(form) {
        // serializeChoices() flattens the choices table into choices_json;
        // defined by the modal's inline script when a choices grid exists.
        if (typeof window.serializeChoices === 'function') {
            try { window.serializeChoices(); } catch (e) { /* no choices grid */ }
        }
        return new FormData(form);
    }

    function save(form) {
        if (form._autosaveInFlight) { form._autosaveQueued = true; return; }
        form._autosaveInFlight = true;
        setState(form, 'saving', 'Saving…');
        var body = serialize(form);
        body.append('autosave', '1');
        fetch(form.getAttribute('hx-post'), {
            method: 'POST',
            headers: { 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value },
            body: body,
        }).then(function (resp) {
            if (resp.ok) {
                return resp.text().then(function (html) {
                    var targetSel = form.getAttribute('hx-target');
                    var target = targetSel && document.querySelector(targetSel);
                    if (target && html) target.outerHTML = html;
                    var iframe = document.getElementById('question-preview-frame');
                    if (iframe) iframe.src = iframe.src;
                    setState(form, 'saved', 'All changes saved');
                });
            }
            if (resp.status === 422) {
                return resp.json().then(function (data) {
                    var first = data.errors && Object.keys(data.errors)[0];
                    var msg = first ? first + ': ' + data.errors[first][0] : 'Check the form';
                    setState(form, 'error', 'Not saved — ' + msg);
                });
            }
            setState(form, 'error', 'Not saved — tap to retry');
        }).catch(function () {
            setState(form, 'error', 'Not saved (offline?) — tap to retry');
        }).finally(function () {
            form._autosaveInFlight = false;
            if (form._autosaveQueued) {
                form._autosaveQueued = false;
                schedule(form);
            }
        });
    }

    function schedule(form) {
        clearTimeout(form._autosaveTimer);
        form._autosaveTimer = setTimeout(function () { save(form); }, DEBOUNCE_MS);
    }

    function attach(root) {
        (root || document).querySelectorAll('form[data-autosave]').forEach(function (form) {
            if (form._autosaveAttached) return;
            form._autosaveAttached = true;
            form.addEventListener('input', function () { schedule(form); });
            form.addEventListener('change', function () { schedule(form); });
            // The indicator doubles as the retry control in the error state.
            var el = indicator(form);
            if (el) {
                el.addEventListener('click', function () {
                    if (el.getAttribute('data-state') === 'error') save(form);
                });
            }
            // Choice rows are added/removed by buttons that don't always fire
            // form events — a click inside the form is a save-worthy signal too.
            form.addEventListener('click', function (e) {
                if (e.target.closest('.choice-remove, .choice-add, [data-choices-mutate]')) {
                    schedule(form);
                }
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () { attach(document); });
    // The modal body arrives via fetch/htmx after load.
    document.body && document.body.addEventListener('htmx:afterSettle', function (e) {
        attach(e.detail && e.detail.target || document);
    });
    // question_form_modal is injected with plain fetch in places — observe.
    new MutationObserver(function () { attach(document); })
        .observe(document.documentElement, { childList: true, subtree: true });
}());
