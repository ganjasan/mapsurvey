/* Respondent bottom-sheet controller (openspec: mobile-adaptive-refactor,
 * respondent-bottom-sheet). Included only when MOBILE_BOTTOM_SHEET is on.
 *
 * Turns the #info_page panel into a three-detent bottom sheet on ≤768px
 * viewports: `peek` (title + progress visible, map free), `half` (default),
 * `full` (long question lists). The existing global toggleInfo(show) — called
 * by every drawing tool when it wants the map — is wrapped so collapse means
 * "snap to peek", never "slide off screen". Desktop keeps the legacy panel:
 * the wrapper delegates when the media query does not match.
 */
(function () {
    'use strict';

    var DETENTS = ['peek', 'half', 'full'];

    function sheetMode() {
        return window.matchMedia('(max-width: 768px)').matches;
    }

    function panel() { return document.getElementById('info_page'); }

    function setDetent(name) {
        var p = panel();
        if (!p) return;
        p.setAttribute('data-detent', name);
        p.classList.remove('hidden');
        DETENTS.forEach(function (d) {
            document.body.classList.toggle('sheet-at-' + d, d === name);
        });
        // Legacy code keys map-control offsets on this class; in sheet mode
        // "sidebar hidden" corresponds to the peek detent.
        document.body.classList.toggle('sidebar-hidden', name === 'peek');
    }

    function currentDetent() {
        var p = panel();
        return (p && p.getAttribute('data-detent')) || 'half';
    }

    function init() {
        var p = panel();
        if (!p) return;
        document.body.classList.add('bottom-sheet-enabled');

        // Grab handle, injected so the template stays flag-agnostic.
        if (!p.querySelector('.sheet-grab-zone')) {
            var zone = document.createElement('div');
            zone.className = 'sheet-grab-zone';
            var bar = document.createElement('div');
            bar.className = 'sheet-grab';
            zone.appendChild(bar);
            p.insertBefore(zone, p.firstChild);

            var startY = null, startDetent = null;
            zone.addEventListener('pointerdown', function (e) {
                if (!sheetMode()) return;
                startY = e.clientY;
                startDetent = currentDetent();
                zone.setPointerCapture(e.pointerId);
            });
            zone.addEventListener('pointerup', function (e) {
                if (startY === null || !sheetMode()) { startY = null; return; }
                var dy = e.clientY - startY;
                startY = null;
                var idx = DETENTS.indexOf(startDetent);
                if (Math.abs(dy) < 12) {
                    // Tap: toggle between peek and half.
                    setDetent(startDetent === 'peek' ? 'half' : 'peek');
                    return;
                }
                if (dy < 0 && idx < DETENTS.length - 1) setDetent(DETENTS[idx + 1]);
                if (dy > 0 && idx > 0) setDetent(DETENTS[idx - 1]);
            });
        }

        // Wrap the legacy toggle: drawing tools call toggleInfo(false) to get
        // the map — in sheet mode that is "snap to peek".
        var legacyToggle = window.toggleInfo;
        window.toggleInfo = function (show) {
            if (sheetMode()) {
                setDetent(show ? 'half' : 'peek');
            } else if (typeof legacyToggle === 'function') {
                legacyToggle(show);
            }
        };

        if (sheetMode()) setDetent('half');

        // Crossing the breakpoint (rotation, resize): reset whichever chrome
        // becomes active so neither mode inherits the other's state.
        window.matchMedia('(max-width: 768px)').addEventListener('change', function (m) {
            if (m.matches) {
                setDetent('half');
            } else {
                DETENTS.forEach(function (d) { document.body.classList.remove('sheet-at-' + d); });
                var pp = panel();
                if (pp) pp.removeAttribute('data-detent');
                if (typeof legacyToggle === 'function') legacyToggle(true);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
