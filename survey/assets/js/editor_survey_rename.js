/* Inline rename of the survey from the editor navbar
 * (openspec: inline-rename-survey-title).
 *
 * The navbar title is the most title-shaped element on the page, and creators
 * click it expecting to rename. This turns that click into the edit it looks
 * like: the button becomes an input, Enter or blur saves, Escape restores.
 *
 * Blur saves rather than cancels, matching editor_autosave.js on question
 * forms — a creator who clicks away has not asked to lose their typing. That
 * makes "clicked a navbar link while editing" a real case: the save request
 * would be cancelled by the navigation, so it goes out with keepalive.
 *
 * The markup this drives is rendered only for viewers who may rename (see the
 * {% survey_title %} tag); this file adds no permission logic of its own.
 */
(function () {
    'use strict';

    var COUNTER_AT = 10;   // characters left before the counter appears

    function commitLabel(root) {
        return root.querySelector('.survey-name__button');
    }

    function showError(root, message) {
        var el = root.querySelector('.survey-name__error');
        if (!el) {
            el = document.createElement('span');
            el.className = 'survey-name__error';
            el.setAttribute('role', 'alert');
            root.appendChild(el);
        }
        el.textContent = message;
    }

    function clearError(root) {
        var el = root.querySelector('.survey-name__error');
        if (el) el.remove();
    }

    function updateCounter(root, input, max) {
        var el = root.querySelector('.survey-name__counter');
        var left = max - input.value.length;
        if (left > COUNTER_AT) {
            if (el) el.remove();
            return;
        }
        if (!el) {
            el = document.createElement('span');
            el.className = 'survey-name__counter';
            root.appendChild(el);
        }
        el.textContent = left;
        el.classList.toggle('is-full', left <= 0);
    }

    function leaveEditMode(root, name) {
        var input = root.querySelector('.survey-name__input');
        if (input) input.remove();
        clearError(root);
        var counter = root.querySelector('.survey-name__counter');
        if (counter) counter.remove();
        var button = commitLabel(root);
        if (button) {
            button.textContent = name;
            button.hidden = false;
            button.focus();
        }
        root.classList.remove('is-editing');
    }

    function save(root, input, original) {
        var value = input.value.trim();
        // The saved name comes back from the server, so any normalisation it
        // does is visible now rather than at the next page load.
        return fetch(root.dataset.renameUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': root.dataset.csrf,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'name=' + encodeURIComponent(value),
            keepalive: true,
        }).then(function (resp) {
            return resp.json().then(function (data) {
                if (resp.ok && data.ok) {
                    leaveEditMode(root, data.name);
                    document.title = document.title.split(original).join(data.name);
                    return true;
                }
                var errors = (data.errors && data.errors.name) || [];
                showError(root, errors[0] || root.dataset.labelError);
                input.focus();
                return false;
            });
        }).catch(function () {
            // Keep the typed value: the creator's text is the only copy of it.
            showError(root, root.dataset.labelError);
            return false;
        });
    }

    function enterEditMode(root) {
        if (root.classList.contains('is-editing')) return;
        var button = commitLabel(root);
        var original = button.textContent.trim();
        var max = parseInt(root.dataset.maxLength, 10);

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'survey-name__input';
        input.value = original;
        input.maxLength = max;
        input.setAttribute('aria-label', root.dataset.labelRename);
        // Freeze the width the title already occupies: growing or shrinking
        // here would reflow the navbar and, below 768px, push the version chip
        // and the ⋯ overflow off the first grid row.
        // + the input's own border and padding, so the text does not start scrolled.
        input.style.width = Math.max(root.offsetWidth + 8, 180) + 'px';

        // editing → saving → done. Anything but 'editing' ignores a further
        // Enter or blur, which matters because leaving edit mode removes the
        // focused input and so fires blur one last time.
        var state = 'editing';
        function finish(commit) {
            if (state !== 'editing') return;
            if (!commit || input.value.trim() === original) {
                state = 'done';
                leaveEditMode(root, original);
                return;
            }
            state = 'saving';
            save(root, input, original).then(function (saved) {
                state = saved ? 'done' : 'editing';
            });
        }

        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); finish(true); }
            else if (e.key === 'Escape') { e.preventDefault(); finish(false); }
        });
        input.addEventListener('input', function () {
            clearError(root);
            updateCounter(root, input, max);
        });
        input.addEventListener('blur', function () { finish(true); });

        button.hidden = true;
        root.classList.add('is-editing');
        root.insertBefore(input, button);
        updateCounter(root, input, max);
        input.focus();
        input.select();
    }

    document.addEventListener('click', function (e) {
        var button = e.target.closest('.survey-name--editable .survey-name__button');
        if (button) enterEditMode(button.closest('.survey-name--editable'));
    });

    /* The same limit, made visible on the slower path: any field marked
     * data-char-counter gets the counter the navbar input has. The survey name
     * in Survey settings carries it, so the two surfaces tell the creator the
     * same thing. Runs on load and after an HTMX swap (the settings panel). */
    function attachCounters(scope) {
        var inputs = (scope || document).querySelectorAll('input[data-char-counter][maxlength]');
        Array.prototype.forEach.call(inputs, function (input) {
            if (input._charCounter) return;
            input._charCounter = true;
            var max = parseInt(input.getAttribute('maxlength'), 10);
            var counter = document.createElement('div');
            counter.className = 'char-counter';
            input.parentNode.insertBefore(counter, input.nextSibling);
            function render() {
                var left = max - input.value.length;
                counter.textContent = left > COUNTER_AT ? '' : left;
                counter.classList.toggle('is-full', left <= 0);
            }
            input.addEventListener('input', render);
            render();
        });
    }

    document.addEventListener('DOMContentLoaded', function () { attachCounters(document); });
    document.addEventListener('htmx:afterSwap', function (e) { attachCounters(e.target); });
})();
