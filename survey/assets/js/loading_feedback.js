/* loading_feedback.js — loading feedback on creator pages (change
 * creator-loading-feedback, issue #337).
 *
 * Two things, one script, included once per creator base template through
 * partials/_loading_feedback.html:
 *
 *   1. A thin progress bar at the top of the viewport while the page waits:
 *      ~150 ms after a same-origin link click or a native form submit (a fast
 *      navigation never shows it), ~300 ms into an HTMX request (polling
 *      excluded). Ends when the page unloads or the request reports back,
 *      success or error.
 *   2. A busy state on the submit button that sent a form: disabled, spinner
 *      in place of its leading icon, aria-busy. A second native submit of the
 *      same form while the first is in flight is dropped.
 *
 * Nothing here is per page. The one knob is `data-no-progress` on a link, a
 * form or an ancestor: no bar, no busy state for it.
 *
 * Public surface (for hand-written fetch() call sites):
 *   LoadingFeedback.start(delayMs?)  -> hold the bar (counted; shown after delay)
 *   LoadingFeedback.done()           -> release one hold; hides at zero
 *   LoadingFeedback.busy(button)     -> busy state (disabled next tick); returns a release function
 *   LoadingFeedback.reset()          -> hide the bar, release every button
 *
 * Why the details are the way they are:
 *   - `click`/`submit` are observed on `window` in the bubble phase, after
 *     every element and document handler ran, so `defaultPrevented` is final:
 *     a gated link, a cancelled confirm(), a form HTMX took over start nothing.
 *   - A busy button is disabled on the next tick, never inside the click: a
 *     disabled submitter is dropped from the form data set (views read the
 *     button's name/value — org switch, publishing widget), and jQuery skips
 *     delegated click handlers on a disabled element, so a synchronous disable
 *     kills Bootstrap's data-toggle (the question modal never opened).
 *   - HTMX busy state is for requests that send something: a form submit with
 *     its submitter, or a button whose verb is not GET. A button that GETs a
 *     pane or a modal body gets the bar only.
 *   - HTMX pairs `htmx:beforeSend` (just before xhr.send; `beforeRequest` can
 *     be cancelled by another listener and then `afterRequest` never fires)
 *     with `htmx:afterRequest`, which htmx fires on load, error, abort and
 *     timeout alike. The pair is keyed on the xhr object.
 *   - `pageshow` with `persisted` is the back/forward cache: the page returns
 *     exactly as it was left, bar up and button disabled, so both are reset.
 *   - A navigation that never unloads the page (a download, Escape) would
 *     leave the bar up forever; a 30 s watchdog resets it. An HTMX request that
 *     never reports back releases after 60 s.
 */
window.LoadingFeedback = (function () {
    'use strict';

    var NAV_DELAY_MS = 150;
    var HTMX_DELAY_MS = 300;
    var NAV_WATCHDOG_MS = 30000;
    var HTMX_WATCHDOG_MS = 60000;
    var SPINNER_CLASS = 'fas fa-spinner fa-spin';

    var reducedMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

    // ── the bar ──
    var root = null, bar = null;
    var holds = 0, visible = false, width = 0;
    var showTimer = null, trickleTimer = null, leaveTimer = null;

    function ensureBar() {
        if (root) return;
        root = document.createElement('div');
        root.className = 'ms-progress';
        root.setAttribute('aria-hidden', 'true');
        bar = document.createElement('div');
        bar.className = 'ms-progress__bar';
        root.appendChild(bar);
        (document.body || document.documentElement).appendChild(root);
    }

    function setWidth(value) {
        width = value;
        bar.style.width = value + '%';
    }

    function show() {
        ensureBar();
        clearTimeout(leaveTimer);
        root.classList.remove('is-leaving');
        if (visible) return;
        visible = true;
        // Back to zero without animating the shrink, then let the transition run.
        bar.style.transition = 'none';
        setWidth(0);
        void root.offsetWidth;
        bar.style.transition = '';
        root.classList.add('is-visible');
        setWidth(reducedMotion ? 60 : 30);
        if (!reducedMotion) {
            trickleTimer = setInterval(function () {
                if (width < 90) setWidth(width + Math.max(0.5, (90 - width) / 8));
            }, 400);
        }
    }

    function hide() {
        if (!visible) return;
        visible = false;
        clearInterval(trickleTimer);
        setWidth(100);
        root.classList.add('is-leaving');
        leaveTimer = setTimeout(function () {
            root.classList.remove('is-visible');
            root.classList.remove('is-leaving');
            setWidth(0);
        }, 450);
    }

    function start(delayMs) {
        holds += 1;
        if (visible || showTimer) return;
        showTimer = setTimeout(function () {
            showTimer = null;
            if (holds > 0) show();
        }, delayMs == null ? NAV_DELAY_MS : delayMs);
    }

    function done() {
        if (holds > 0) holds -= 1;
        if (holds > 0) return;
        if (showTimer) { clearTimeout(showTimer); showTimer = null; }
        hide();
    }

    // ── busy buttons ──
    var busyRecords = [];

    function isButtonLike(el) {
        if (!el || !el.tagName) return false;
        if (el.tagName === 'BUTTON') return true;
        if (el.tagName === 'INPUT') {
            var t = (el.type || '').toLowerCase();
            return t === 'submit' || t === 'button' || t === 'image';
        }
        return false;
    }

    function isSubmitter(el) {
        if (!el || !el.tagName) return false;
        if (el.tagName === 'BUTTON') return !el.type || el.type.toLowerCase() === 'submit';
        if (el.tagName === 'INPUT') {
            var t = (el.type || '').toLowerCase();
            return t === 'submit' || t === 'image';
        }
        return false;
    }

    // `disabled` lands on the next tick (see the header). Returns the release
    // function; a no-op for a button already busy.
    function busy(btn) {
        if (!isButtonLike(btn) || btn.dataset.msBusy) return function () {};
        var rec = {
            btn: btn,
            wasDisabled: btn.disabled,
            icon: null,
            iconClass: null,
            spinner: null,
            disableTimer: null,
            released: false,
        };
        btn.dataset.msBusy = '1';
        btn.classList.add('is-busy');
        btn.setAttribute('aria-busy', 'true');
        if (btn.tagName === 'BUTTON') {
            var first = btn.firstElementChild;
            if (first && first.tagName === 'I' && /(^|\s)fa-/.test(first.className)) {
                rec.icon = first;
                rec.iconClass = first.className;
                first.className = SPINNER_CLASS;
            } else {
                rec.spinner = document.createElement('i');
                rec.spinner.className = SPINNER_CLASS + ' ms-busy-spinner';
                rec.spinner.setAttribute('aria-hidden', 'true');
                btn.insertBefore(rec.spinner, btn.firstChild);
            }
        }
        rec.disableTimer = setTimeout(function () {
            rec.disableTimer = null;
            if (!rec.released) btn.disabled = true;
        }, 0);
        rec.release = function () {
            if (rec.released) return;
            rec.released = true;
            clearTimeout(rec.disableTimer);
            btn.disabled = rec.wasDisabled;
            btn.classList.remove('is-busy');
            btn.removeAttribute('aria-busy');
            delete btn.dataset.msBusy;
            if (rec.icon) rec.icon.className = rec.iconClass;
            if (rec.spinner && rec.spinner.parentNode) rec.spinner.parentNode.removeChild(rec.spinner);
            var i = busyRecords.indexOf(rec);
            if (i >= 0) busyRecords.splice(i, 1);
        };
        busyRecords.push(rec);
        return rec.release;
    }

    function releaseAll() {
        busyRecords.slice().forEach(function (rec) { rec.release(); });
    }

    // ── native navigation ──
    var navPending = false, navWatchdog = null;

    function beginNavigation() {
        if (navPending) return;
        navPending = true;
        start(NAV_DELAY_MS);
        navWatchdog = setTimeout(reset, NAV_WATCHDOG_MS);
    }

    function reset() {
        clearTimeout(navWatchdog);
        navWatchdog = null;
        navPending = false;
        releaseAll();
        document.querySelectorAll('form[data-ms-submitting]').forEach(function (form) {
            delete form.dataset.msSubmitting;
        });
        holds = 0;
        if (showTimer) { clearTimeout(showTimer); showTimer = null; }
        hide();
    }

    function hasHtmxAttribute(el) {
        var attrs = el.attributes;
        for (var i = 0; i < attrs.length; i++) {
            var n = attrs[i].name;
            if (n.indexOf('hx-') === 0 || n.indexOf('data-hx-') === 0) return true;
        }
        return false;
    }

    function isPlainNavigation(a) {
        if (a.hasAttribute('download') || a.hasAttribute('data-toggle')) return false;
        if (a.closest('[data-no-progress]')) return false;
        var target = (a.getAttribute('target') || '').toLowerCase();
        if (target && target !== '_self') return false;
        if (hasHtmxAttribute(a)) return false;
        var href = (a.getAttribute('href') || '').trim();
        if (href === '' || href.charAt(0) === '#') return false;
        var url;
        try { url = new URL(a.href, window.location.href); } catch (err) { return false; }
        if (url.protocol !== 'http:' && url.protocol !== 'https:') return false;
        if (url.origin !== window.location.origin) return false;
        // Same document, only the fragment differs: no load happens.
        if (url.hash && url.pathname === window.location.pathname && url.search === window.location.search) return false;
        return true;
    }

    window.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var t = e.target;
        if (!t || typeof t.closest !== 'function') return;
        var a = t.closest('a[href]');
        if (!a || !isPlainNavigation(a)) return;
        beginNavigation();
    });

    function submitterOf(e, form) {
        if (e.submitter) return e.submitter;
        var active = document.activeElement;
        if (active && active.form === form && isSubmitter(active)) return active;
        var candidates = form.querySelectorAll('button, input[type="submit"], input[type="image"]');
        for (var i = 0; i < candidates.length; i++) {
            if (isSubmitter(candidates[i]) && candidates[i].form === form) return candidates[i];
        }
        return null;
    }

    window.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        if (form.dataset.msSubmitting) {
            // The first submit is on its way to the server; drop this one.
            e.preventDefault();
            return;
        }
        if (e.defaultPrevented) return;
        if (hasHtmxAttribute(form)) return;
        var target = (form.getAttribute('target') || '').toLowerCase();
        if (target && target !== '_self') return;
        if (form.closest('[data-no-progress]')) return;
        form.dataset.msSubmitting = '1';
        var btn = submitterOf(e, form);
        if (btn) busy(btn);
        beginNavigation();
    });

    window.addEventListener('pageshow', function (e) {
        if (e.persisted) reset();
    });

    // ── HTMX ──
    function finishRequest(rec) {
        if (rec.finished) return;
        rec.finished = true;
        clearTimeout(rec.timer);
        done();
        if (rec.release) rec.release();
    }

    document.addEventListener('htmx:beforeSend', function (e) {
        var d = e.detail || {};
        var elt = d.elt, xhr = d.xhr;
        if (!xhr || xhr.msLoadingFeedback) return;
        if (elt && typeof elt.closest === 'function' && elt.closest('[data-no-progress]')) return;
        var trigger = elt && elt.getAttribute
            ? (elt.getAttribute('hx-trigger') || elt.getAttribute('data-hx-trigger') || '')
            : '';
        if (/\bevery\b/.test(trigger)) return;
        var rec = { finished: false, release: null, timer: null };
        xhr.msLoadingFeedback = rec;
        start(HTMX_DELAY_MS);
        var btn = null;
        var verb = ((d.requestConfig && d.requestConfig.verb) || 'get').toLowerCase();
        if (isButtonLike(elt)) {
            if (verb !== 'get') btn = elt;
        } else if (elt && elt.tagName === 'FORM') {
            var ev = d.requestConfig && d.requestConfig.triggeringEvent;
            if (ev && ev.submitter) btn = ev.submitter;
        }
        if (btn) rec.release = busy(btn);
        rec.timer = setTimeout(function () { finishRequest(rec); }, HTMX_WATCHDOG_MS);
    });

    document.addEventListener('htmx:afterRequest', function (e) {
        var xhr = e.detail && e.detail.xhr;
        if (xhr && xhr.msLoadingFeedback) finishRequest(xhr.msLoadingFeedback);
    });

    return { start: start, done: done, busy: busy, reset: reset };
})();
