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

    function apply() {
        var data = document.getElementById('section-data');
        var form = document.getElementById('section_question_form');
        if (!data || !form) return;
        var raw = data.getAttribute('data-visibility-rules');
        if (!raw) return;
        var rules;
        try { rules = JSON.parse(raw); } catch (e) { return; }

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
