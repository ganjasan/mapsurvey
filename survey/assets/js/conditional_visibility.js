/* Conditional visibility — respondent client side (openspec:
 * conditional-question-visibility).
 *
 * Same-section dependents are rendered in the DOM and toggled here as the
 * controlling answer changes; their inputs are disabled while hidden so they
 * never post. The server independently discards answers to hidden questions,
 * so this module is presentation only — nothing here is trusted.
 *
 * Rules come from #section-data[data-visibility-rules]:
 *   {"<question_code>": {"question_code": "<controller>", "choice_codes": [..]}}
 * or, for "answered (any option)" rules (#339),
 *   {"<question_code>": {"question_code": "<controller>", "answered": true}}
 * Initialises idempotently on page load and on every HTMX section swap.
 *
 * Pop-up rules (sub-questions ruled by an earlier choice sub-question of the
 * same pop-up, #338) come from #section-data[data-popup-visibility-rules] in
 * the same shape, keyed by sub-question code. They are applied per pop-up
 * <form> through window.ConditionalVisibility.bindPopup(formEl), which the
 * shell's initPopupFields() calls after restoring a feature's values — so a
 * reopened feature starts in the state its stored answers decide.
 *
 * Question groups (change question-groups, #340): a group's rule rides the
 * same maps under the key "group:<code>" and toggles the
 * .question-group[data-group-code] element, disabling every input inside.
 * The server orders a group's key before its members' keys, and a member's
 * own rule never re-enables a card that sits in a hidden group. This module
 * also owns the collapsible group's toggle (window.QuestionGroups).
 */
(function () {
    'use strict';

    function controllerValues(form, name) {
        var values = [];
        var inputs = form.querySelectorAll('[name="' + name + '"]');
        inputs.forEach(function (el) {
            if (el.disabled) return;
            var tag = el.tagName.toLowerCase();
            var type = (el.type || '').toLowerCase();
            if (type === 'radio' || type === 'checkbox') {
                if (el.checked && el.value !== '') values.push(parseInt(el.value, 10));
            } else if (tag === 'select') {
                if (el.value !== '') values.push(parseInt(el.value, 10));
            }
        });
        return values;
    }

    var GROUP_PREFIX = 'group:';

    function cardFor(form, code) {
        if (code.indexOf(GROUP_PREFIX) === 0) {
            return form.querySelector('.question-group[data-group-code="' + code.slice(GROUP_PREFIX.length) + '"]');
        }
        return form.querySelector('.question-card[data-field-name="' + code + '"]');
    }

    // Hidden itself or inside a hidden group.
    function isHidden(el) {
        if (!el) return false;
        if (el.hidden) return true;
        var group = el.parentElement && el.parentElement.closest('.question-group');
        return !!(group && group.hidden);
    }

    function readRules(attr) {
        var data = document.getElementById('section-data');
        if (!data) return null;
        var raw = data.getAttribute(attr);
        if (!raw) return null;
        try { return JSON.parse(raw); } catch (e) { return null; }
    }

    function applyRules(form, rules) {
        // Insertion order is section order, and controllers always come before
        // their dependents, so one pass settles cascades too.
        Object.keys(rules).forEach(function (code) {
            var rule = rules[code];
            var card = cardFor(form, code);
            if (!card) return;
            var controllerCard = cardFor(form, rule.question_code);
            var controllerHidden = isHidden(controllerCard);
            var answered = controllerHidden ? [] : controllerValues(form, rule.question_code);
            var visible = rule.answered
                ? answered.length > 0
                : rule.choice_codes.some(function (c) {
                    return answered.indexOf(c) !== -1;
                });
            card.hidden = !visible;
            // A member of a hidden group stays disabled whatever its own rule says.
            var enabled = visible && !isHidden(card);
            card.querySelectorAll('input, textarea, select').forEach(function (el) {
                el.disabled = !enabled;
            });
        });
    }

    function apply() {
        var form = document.getElementById('section_question_form');
        var rules = readRules('data-visibility-rules');
        if (!form || !rules) return;
        applyRules(form, rules);
    }

    // Pop-up side: one <form> per placed feature / opened object. Hidden
    // cards' inputs are disabled, so serializeArray() never carries them into
    // the feature's properties or the object's fields. Binds once per form.
    function applyPopup(form) {
        var rules = readRules('data-popup-visibility-rules');
        if (!form || !rules) return;
        applyRules(form, rules);
        contentChanged(form);
    }

    // A pop-up is sized when it opens; a card shown, hidden or opened later
    // must ask the page to re-measure it (the shell answers with popup.update()).
    function contentChanged(el) {
        if (el) el.dispatchEvent(new CustomEvent('ms:popup-content-changed', { bubbles: true }));
    }

    function bindPopup(form) {
        if (!form) return;
        if (!form.dataset.cvBound) {
            form.dataset.cvBound = '1';
            form.addEventListener('change', function () { applyPopup(form); });
        }
        applyPopup(form);
    }

    // Names of the fields a pop-up form currently hides — the shell drops
    // them from a feature's properties on Apply/close, where a value from an
    // earlier pick would otherwise survive in the feature.
    function hiddenFieldNames(form) {
        var names = [];
        if (!form) return names;
        form.querySelectorAll('.question-card[data-field-name]').forEach(function (card) {
            if (isHidden(card)) names.push(card.getAttribute('data-field-name'));
        });
        return names;
    }

    window.ConditionalVisibility = {
        bindPopup: bindPopup,
        hiddenFieldNames: hiddenFieldNames,
        isHidden: isHidden
    };

    // --- Collapsible groups -------------------------------------------------
    function setOpen(group, open) {
        var toggle = group && group.querySelector(':scope > .question-group__head > .question-group__toggle');
        var body = group && group.querySelector(':scope > .question-group__body');
        if (!toggle || !body) return;
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        body.hidden = !open;
        contentChanged(group);
    }

    window.QuestionGroups = {
        // Open the collapsed group around `el` (the required check calls this
        // before scrolling to an unanswered card); flags it while invalid.
        reveal: function (el, invalid) {
            var group = el && el.closest && el.closest('.question-group--collapsible');
            if (!group) return;
            setOpen(group, true);
            group.classList.toggle('question-group--error', !!invalid);
        }
    };

    // Capture phase: Leaflet stops click propagation inside map pop-ups.
    document.addEventListener('click', function (e) {
        var toggle = e.target.closest && e.target.closest('.question-group__toggle');
        if (!toggle) return;
        var group = toggle.closest('.question-group');
        setOpen(group, toggle.getAttribute('aria-expanded') !== 'true');
    }, true);
    document.addEventListener('change', function (e) {
        var group = e.target.closest && e.target.closest('.question-group--error');
        if (group) group.classList.remove('question-group--error');
    });

    function bind() {
        var data = document.getElementById('section-data');
        var form = document.getElementById('section_question_form');
        if (!data || !form || form.dataset.cvBound) { apply(); return; }
        form.dataset.cvBound = '1';
        form.addEventListener('change', apply);
        apply();
    }

    document.addEventListener('DOMContentLoaded', bind);
    document.addEventListener('htmx:afterSwap', bind);
})();
