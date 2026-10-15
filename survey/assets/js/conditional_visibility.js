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
 * Initialises idempotently on page load and on every HTMX section swap.
 *
 * Pop-up rules (sub-questions ruled by an earlier choice sub-question of the
 * same pop-up, #338) come from #section-data[data-popup-visibility-rules] in
 * the same shape, keyed by sub-question code. They are applied per pop-up
 * <form> through window.ConditionalVisibility.bindPopup(formEl), which the
 * shell's initPopupFields() calls after restoring a feature's values — so a
 * reopened feature starts in the state its stored answers decide.
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

    function cardFor(form, code) {
        return form.querySelector('.question-card[data-field-name="' + code + '"]');
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
            var controllerHidden = controllerCard ? controllerCard.hidden : false;
            var answered = controllerHidden ? [] : controllerValues(form, rule.question_code);
            var visible = rule.choice_codes.some(function (c) {
                return answered.indexOf(c) !== -1;
            });
            card.hidden = !visible;
            card.querySelectorAll('input, textarea, select').forEach(function (el) {
                el.disabled = !visible;
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
        form.querySelectorAll('.question-card[hidden][data-field-name]').forEach(function (card) {
            names.push(card.getAttribute('data-field-name'));
        });
        return names;
    }

    window.ConditionalVisibility = {
        bindPopup: bindPopup,
        hiddenFieldNames: hiddenFieldNames
    };

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
