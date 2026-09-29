/* htmx 1.9's htmx.ajax() rejects its returned promise with a bare reject()
 * (value: undefined) on network error, abort, timeout, missing target and
 * invalid path. An undiagnosable rejection nobody can act on: attach a no-op
 * handler here, once, instead of at every call site. Failures stay observable
 * through htmx's own events (htmx:sendError, htmx:responseError, htmx:timeout,
 * htmx:targetError).
 *
 * The original promise is returned unchanged — a rejection is NOT converted
 * into a fulfilment. That also means a derived promise is not covered: a call
 * site chaining .then() must pass its own rejection handler.
 *
 * Must load right after the htmx <script> in every template that includes it
 * (HtmxPromiseGuardTest enforces the pairing). */
(function () {
    'use strict';
    if (!window.htmx || typeof window.htmx.ajax !== 'function') return;
    var ajax = window.htmx.ajax;
    window.htmx.ajax = function () {
        var p = ajax.apply(this, arguments);
        if (p && typeof p.catch === 'function') p.catch(function () {});
        return p;
    };
})();
