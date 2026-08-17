/**
 * Live password checklist for the registration form.
 *
 * Progressive enhancement over the server-rendered <ul data-password-checklist>:
 * without this script the rules are still listed, just not ticked off. Nothing
 * here blocks submission — the server is the authority on whether a password is
 * accepted. See survey/password_rules.py for how the rules are derived from
 * AUTH_PASSWORD_VALIDATORS.
 *
 * Fidelity rule: a check may be permissive (report "ok" where the server would
 * reject) but must never be stricter than the server. Claiming a violation the
 * server would accept teaches people to ignore the checklist. Both notCommon
 * and notSimilar are approximations and deliberately err that way.
 */
(function () {
    'use strict';

    // Django ships a 20k-entry common-password list; shipping it to the browser
    // is not worth the bytes. This covers the passwords people actually try
    // first. Anything not listed passes here and is caught server-side.
    var COMMON = [
        'password', 'password1', '12345678', '123456789', '1234567890',
        'qwerty123', 'qwertyuiop', 'iloveyou', 'princess', 'admin123',
        'welcome1', 'abc12345', 'letmein1', 'monkey12', 'football',
        'password123', 'sunshine', 'baseball', 'trustno1', 'superman'
    ];

    var CHECKS = {
        minLength: function (value, item) {
            var min = parseInt(item.getAttribute('data-min-length'), 10) || 8;
            return value.length >= min;
        },
        notNumeric: function (value) {
            return !/^\d+$/.test(value);
        },
        notCommon: function (value) {
            return COMMON.indexOf(value.toLowerCase()) === -1;
        },
        notSimilar: function (value, item, context) {
            // Django uses SequenceMatcher at a 0.7 ratio against the user's
            // other attributes. Reproducing that faithfully in the browser is
            // not worth it; containment in either direction catches the common
            // case (password reused from the email local part) and stays
            // permissive everywhere else.
            var lower = value.toLowerCase();
            if (!lower) { return false; }
            for (var i = 0; i < context.length; i++) {
                var other = context[i].toLowerCase();
                if (other.length < 4) { continue; }
                if (lower.indexOf(other) !== -1 || other.indexOf(lower) !== -1) {
                    return false;
                }
            }
            return true;
        }
    };

    function contextValues(list, form) {
        var names = (list.getAttribute('data-similar-fields') || '').split(',');
        var values = [];
        names.forEach(function (name) {
            var field = form.querySelector('[name="' + name.trim() + '"]');
            if (!field || !field.value) { return; }
            values.push(field.value);
            // The local part of an email is what people actually reuse.
            var at = field.value.indexOf('@');
            if (at > 0) { values.push(field.value.slice(0, at)); }
        });
        return values;
    }

    function evaluate(list, password, form) {
        var context = contextValues(list, form);
        var empty = password.length === 0;
        list.querySelectorAll('[data-rule]').forEach(function (item) {
            var check = CHECKS[item.getAttribute('data-rule')];
            if (!check) { return; }
            if (empty) {
                // Neutral until they start typing — an untouched field covered
                // in red crosses reads as failure before any attempt was made.
                item.classList.remove('is-met', 'is-unmet', 'is-suggested');
                return;
            }
            var met = check(password, item, context);
            var advisory = item.hasAttribute('data-advisory');
            item.classList.toggle('is-met', met);
            // An advisory rule is not enforced anywhere, so a failed one is a
            // suggestion, not an error. Rendering it like a blocking failure
            // would tell the user the form will reject them when it will not.
            item.classList.toggle('is-unmet', !met && !advisory);
            item.classList.toggle('is-suggested', !met && advisory);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-password-checklist]').forEach(function (list) {
            var form = list.closest('form');
            if (!form) { return; }
            var password = form.querySelector('[name="password1"]');
            if (!password) { return; }

            var rerun = function () { evaluate(list, password.value, form); };
            password.addEventListener('input', rerun);
            // The similarity rule depends on the other fields, so re-evaluate
            // when they change too.
            (list.getAttribute('data-similar-fields') || '').split(',').forEach(function (name) {
                var field = form.querySelector('[name="' + name.trim() + '"]');
                if (field) { field.addEventListener('input', rerun); }
            });
            rerun();
        });
    });
}());
