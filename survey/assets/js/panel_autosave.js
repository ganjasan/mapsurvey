/* Autosave for editor panels (openspec: fix-panel-autosave-error-reporting).
 *
 * Scope: the panels that save without a Save button — Survey settings, the
 * Thanks page, Public results. Question edit forms keep `editor_autosave.js`:
 * they swap a rendered list item back into the page and answer 422, while
 * these post a form and answer JSON.
 *
 * The point of this module is the failure path. All three panels used to end
 * their save with `.catch(function(){ setStatus('error'); })`, which threw away
 * the `errors` map the views send with a 400 — so a creator whose Redirect URL
 * was rejected saw "Not saved — retry" naming no field, and retrying re-posted
 * the same invalid value forever. Replay Vision scored that session 4.0/10
 * frustration on 2026-09-21 (backlog #187).
 *
 * So a failure is one of two kinds:
 *   validation — 400 with {errors: {field: [msg]}}. Name the field by the label
 *                the creator reads, mark it, and offer NO retry: the value has
 *                to change first.
 *   transport  — anything else (network, 403, 5xx). Say so, and let a click on
 *                the indicator re-send.
 *
 *   PanelAutosave.attach(form, {
 *       statusEl,            // defaults to [data-autosave-status] inside form
 *       debounceMs,          // default 600
 *       beforeSave,          // called before FormData is built (Quill sync)
 *       exclude,             // selector: fields that must not trigger or post
 *       onSaved,             // (data) => void, after a successful save
 *       labels,              // {saving, saved, offline, notSaved}
 *   }) -> { save, saveNow, detach }
 */
(function () {
    'use strict';

    var DEBOUNCE_MS = 600;

    function csrfOf(form, fd) {
        return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
            fd.get('csrfmiddlewaretoken') || '';
    }

    // The creator reads labels, not form field names: "redirect_url" means
    // nothing next to the input that says "Redirect URL". Fall back to the
    // name only when no label is rendered for the field.
    function labelFor(form, name) {
        var field = form.querySelector('[name="' + name + '"]');
        if (field) {
            if (field.id) {
                var forLabel = form.querySelector('label[for="' + field.id + '"]');
                if (forLabel && forLabel.textContent.trim()) return forLabel.textContent.trim();
            }
            var wrapping = field.closest('label');
            if (wrapping && wrapping.textContent.trim()) return wrapping.textContent.trim();
        }
        return name;
    }

    // A no-op handle rather than null: these panels are HTMX partials, and a
    // caller that stores `autosave.save` as its debounced handler must not
    // have to guard every call site against a panel that failed to render.
    function noop() {}
    var INERT = { save: noop, saveNow: noop, detach: noop };

    function attach(form, o) {
        if (!form) return INERT;
        o = o || {};
        if (form._panelAutosave) return form._panelAutosave;

        var labels = o.labels || {};
        var statusEl = o.statusEl || form.querySelector('[data-autosave-status]');
        var exclude = o.exclude || null;
        var timer = null, inFlight = false, queued = false, detached = false;
        var marked = [];

        function setStatus(state, message) {
            if (!statusEl) return;
            var span = statusEl.querySelector('span') || statusEl;
            statusEl.classList.remove('is-error', 'is-saving', 'is-retryable');
            statusEl.setAttribute('data-state', state);
            if (state === 'saving') {
                span.textContent = message || labels.saving || 'Saving…';
                statusEl.classList.add('is-saving');
            } else if (state === 'saved') {
                span.textContent = message || labels.saved || 'Saved';
            } else {
                span.textContent = message;
                statusEl.classList.add('is-error');
                // Only a transport failure is worth clicking. A validation
                // failure re-posts the same value and fails the same way, so
                // the indicator stays inert and says nothing about retrying.
                if (state === 'error-transport') statusEl.classList.add('is-retryable');
            }
        }

        function clearMarks() {
            marked.forEach(function (el) { el.classList.remove('is-invalid'); });
            marked = [];
        }

        function markInvalid(name) {
            var field = form.querySelector('[name="' + name + '"]');
            if (!field) return;
            field.classList.add('is-invalid');
            marked.push(field);
        }

        // A 400 from these panels carries {ok: false, errors: {field: [msg]}}.
        // Anything else — a 403 from a swapped-away panel, a 5xx, a body that
        // is not JSON — is a transport failure: nothing here tells the creator
        // which value to change.
        function reportFailure(resp) {
            if (!resp || resp.status !== 400 || typeof resp.json !== 'function') {
                setStatus('error-transport', labels.offline || 'Not saved — tap to retry');
                return Promise.resolve();
            }
            return resp.json().then(function (data) {
                var errors = data && data.errors;
                var name = errors && Object.keys(errors)[0];
                if (!name) throw new Error('no field errors');
                var messages = errors[name];
                var message = Array.isArray(messages) ? messages[0] : messages;
                clearMarks();
                markInvalid(name);
                setStatus('error-validation',
                    (labels.notSaved || 'Not saved') + ' — ' + labelFor(form, name) + ': ' + message);
            }).catch(function () {
                setStatus('error-transport', labels.offline || 'Not saved — tap to retry');
            });
        }

        function saveNow() {
            clearTimeout(timer);
            if (detached || !document.body.contains(form)) { detach(); return; }
            if (inFlight) { queued = true; return; }
            if (typeof o.beforeSave === 'function') o.beforeSave();

            var fd = new FormData(form);
            // Excluded controls sit inside the form for layout only and save
            // through their own endpoints; keep their values out of the POST
            // as well as out of the triggers.
            if (exclude) {
                form.querySelectorAll(exclude).forEach(function (field) {
                    if (field.name) fd.delete(field.name);
                });
            }
            inFlight = true;
            setStatus('saving');
            fetch(form.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfOf(form, fd) },
                body: fd,
            }).then(function (resp) {
                if (!resp.ok) return reportFailure(resp);
                // A panel that answers 204, or HTML, is still a success.
                return resp.json().catch(function () { return { ok: true }; }).then(function (data) {
                    clearMarks();
                    setStatus('saved');
                    if (typeof o.onSaved === 'function') o.onSaved(data);
                });
            }).catch(function () {
                setStatus('error-transport', labels.offline || 'Not saved — tap to retry');
            }).finally(function () {
                inFlight = false;
                if (queued) { queued = false; schedule(); }
            });
        }

        function schedule() {
            clearTimeout(timer);
            timer = setTimeout(saveNow, o.debounceMs || DEBOUNCE_MS);
        }

        function excluded(field) {
            if (field.name === 'csrfmiddlewaretoken') return true;
            if (field.hasAttribute('data-no-autosave')) return true;
            return !!(exclude && field.matches(exclude));
        }

        form.querySelectorAll('input, select, textarea').forEach(function (field) {
            if (excluded(field)) return;
            var t = field.type;
            if (field.tagName === 'SELECT' || t === 'checkbox' || t === 'radio' || t === 'file') {
                field.addEventListener('change', saveNow);
            } else {
                field.addEventListener('input', schedule);
                field.addEventListener('change', saveNow);
            }
        });

        if (statusEl) {
            statusEl.addEventListener('click', function () {
                if (statusEl.classList.contains('is-retryable')) saveNow();
            });
        }

        function detach() {
            detached = true;
            clearTimeout(timer);
        }

        form._panelAutosave = { save: schedule, saveNow: saveNow, detach: detach };
        return form._panelAutosave;
    }

    window.PanelAutosave = { attach: attach };
})();
