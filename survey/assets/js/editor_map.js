/* EditorMap — one lifecycle for every Leaflet map the editor mounts into a
 * fragment that HTMX may swap away (openspec: responses-map-lifecycle).
 *
 *   var map = EditorMap.mount(containerOrId, leafletOptions, function (map) {
 *       // runs once the container has a size: add layers, fitBounds
 *   });
 *   EditorMap.dispose(containerOrId);
 *   EditorMap.get(containerOrId);
 *
 * Three questions every map on the Responses page used to answer on its own,
 * differently, and one of them wrongly enough to kill the drawer for the rest
 * of a session (PostHog 01a0a273, three issues in five seconds):
 *
 *   Is there already a map here?  The instance lives ON THE ELEMENT, never in a
 *   page global. When HTMX discards the element the reference goes with it;
 *   there is nothing left to call remove() on later. A global that outlived
 *   its DOM is what threw `reading 'parentNode'` and then "Map container is
 *   being reused by another instance" on every later open.
 *
 *   How do I get rid of it?  dispose() runs on htmx:beforeCleanupElement --
 *   while the container is still attached, so Leaflet's own remove() can
 *   unbind everything it bound -- and never throws. Leaflet 1.4's remove()
 *   deletes the container's _leaflet_id FIRST and tears layers down AFTER, so
 *   a layer that throws leaves the id half-cleared; dispose() finishes the job
 *   itself whatever remove() managed.
 *
 *   When can I draw?  `ready` waits for a non-zero container size, observed
 *   with ResizeObserver rather than guessed with a timer. Drawing into a 0x0
 *   map is what threw `reading 'min'` on the first polygon.
 */
(function () {
    'use strict';

    // Maps whose container may still be in the document. Swept at every mount:
    // a removal path that bypasses HTMX (jQuery .html(), a future framework)
    // must not leave a map behind -- a hook that silently stops matching is
    // how this class of defect comes back.
    var live = [];

    function resolve(container) {
        return typeof container === 'string' ? document.getElementById(container) : container;
    }

    function forget(map) {
        var i = live.indexOf(map);
        if (i !== -1) live.splice(i, 1);
    }

    function hasSize(map) {
        var s = map.getSize();
        return s.x > 0 && s.y > 0;
    }

    /* Calls fn(map) once the container has a size; returns a function that
       cancels the wait. invalidateSize() first, so Leaflet's own measurement
       matches the size fn is about to draw into. */
    function whenSized(map, fn) {
        if (hasSize(map)) {
            map.invalidateSize();
            fn(map);
            return function () {};
        }
        var el = map.getContainer();
        var stopped = false, observer = null, frame = null;
        function stop() {
            stopped = true;
            if (observer) { observer.disconnect(); observer = null; }
            if (frame) { cancelAnimationFrame(frame); frame = null; }
        }
        function check() {
            if (stopped || !hasSize(map)) return;
            stop();
            map.invalidateSize();
            fn(map);
        }
        if (window.ResizeObserver) {
            observer = new ResizeObserver(check);
            observer.observe(el);
        } else {
            (function poll() {
                if (stopped) return;
                check();
                if (!stopped) frame = requestAnimationFrame(poll);
            })();
        }
        return stop;
    }

    function dispose(container) {
        var el = resolve(container);
        if (!el) return;
        var map = el._editorMap;
        if (map && map._editorMapCleanup) map._editorMapCleanup();
        try {
            if (map) map.remove();
        } catch (e) {
            // A half-torn map: remove() threw part-way. The map is being thrown
            // away; an exception here is what turned one bad draw into a dead
            // drawer for the rest of the session. Finish by hand below.
        }
        // Independent of where remove() stopped: the id that gates "reused by
        // another instance", the classes, and any panes left behind.
        try { delete el._leaflet_id; } catch (e) { el._leaflet_id = undefined; }
        el.className = el.className.replace(/(^|\s)leaflet-\S+/g, ' ').replace(/\s+/g, ' ').trim();
        while (el.firstChild) el.removeChild(el.firstChild);
        el._editorMap = null;
        if (map) forget(map);
    }

    function sweep() {
        live.slice().forEach(function (map) {
            var el = map.getContainer && map.getContainer();
            if (!el || !document.body.contains(el)) dispose(el);
        });
    }

    function mount(container, options, ready) {
        var el = resolve(container);
        if (!el) return null;
        sweep();
        // Mounted again on the same element (a re-initialised pane, a reopened
        // modal), or a raw L.map() elsewhere left its id behind: clear first so
        // L.map() below cannot throw "reused by another instance".
        if (el._editorMap || el._leaflet_id) dispose(el);

        var map = L.map(el, options || {});
        el._editorMap = map;
        live.push(map);

        var stopWait = null;
        function onCleanup(evt) {
            // Descendants' cleanup events bubble through here; act on our own.
            if (evt.target === el) dispose(el);
        }
        el.addEventListener('htmx:beforeCleanupElement', onCleanup);
        map._editorMapCleanup = function () {
            if (stopWait) { stopWait(); stopWait = null; }
            el.removeEventListener('htmx:beforeCleanupElement', onCleanup);
            map._editorMapCleanup = null;
        };

        if (typeof ready === 'function') {
            stopWait = whenSized(map, function (m) {
                stopWait = null;
                // Disposed while waiting: the drawer closed before layout.
                if (el._editorMap === m) ready(m);
            });
        }
        return map;
    }

    function get(container) {
        var el = resolve(container);
        return el ? (el._editorMap || null) : null;
    }

    window.EditorMap = { mount: mount, dispose: dispose, get: get, whenSized: whenSized };
})();
