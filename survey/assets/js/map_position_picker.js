/*
 * Map position picker for the creator-facing editor
 * (openspec: map-picker-centre-autosave).
 *
 * The position IS the centre of the map. A fixed pin marks it; dragging,
 * zooming, a place-search result and "My location" all move the map and so
 * set the position. There is nothing to click and nothing to press: every
 * settled move is saved after a short pause, and an indicator says whether
 * it went through. The three editor pickers (section modal, settings page,
 * settings panel) used to take the position from a CLICK and save on a
 * button; a creator who dragged the map — the create page's model — saved the
 * survey default into two sections and never saw why.
 *
 *   var picker = MapPositionPicker.attach(map, {
 *       url, csrfToken,               // POST target and header
 *       coordsEl, indicatorEl,        // label under the map; .autosave-indicator
 *       inherit: {checkbox, lat, lng, zoom},   // section modal only
 *       extraFields: function () { return {use_geolocation: '1'}; },
 *       watch: [checkbox, select],    // save now on their `change`
 *       locate: true,                 // "My location" control
 *       labels: {centre, zoom, inheriting, saving, saved, error,
 *                myLocation, locating, locateFailed, noGeolocation}
 *   });
 *   picker.touched()   // a creator gesture the module cannot see (search result)
 *   picker.rebase()    // "this view is already the saved one": after a courtesy
 *                      // geolocation flight, so it is not written as a decision
 *
 * Inherit: ticked → fly to the survey default, dim the pin, save the cleared
 * position at once. While ticked, moves are not saved (the fly itself must not
 * come back as a position). Any creator gesture unticks it — moving the map is
 * how a section gets a position of its own. Programmatic moves never untick.
 */
(function (window, document) {
    'use strict';

    // Same pause editor_autosave.js gives a question form.
    var DEBOUNCE_MS = 800;

    function attach(map, options) {
        var o = options || {};
        var labels = o.labels || {};
        var inherit = o.inherit || null;
        var coordsEl = o.coordsEl || null;
        var indicatorEl = o.indicatorEl || null;

        // The pin sits over the map container, which .picker-map positions.
        var pin = document.createElement('div');
        pin.className = 'map-center-pin';
        pin.setAttribute('aria-hidden', 'true');
        var pinIcon = document.createElement('i');
        pinIcon.className = 'fas fa-map-marker-alt';
        pin.appendChild(pinIcon);
        map.getContainer().appendChild(pin);

        var inFlight = false, queued = false, timer = null;
        var lastKey = null;
        // Everything attached outside this closure, so detach() can undo it.
        var teardown = [];
        var detached = false;

        function on(target, event, handler, opts) {
            target.addEventListener(event, handler, opts);
            teardown.push(function () { target.removeEventListener(event, handler, opts); });
        }

        function mapOn(event, handler) {
            map.on(event, handler);
            teardown.push(function () { map.off(event, handler); });
        }

        function inheriting() {
            return !!(inherit && inherit.checkbox && inherit.checkbox.checked);
        }

        function current() {
            var c = map.getCenter();
            return { lat: c.lat, lng: c.lng, zoom: Math.round(map.getZoom()) };
        }

        // What a save would write. Equal keys mean nothing to save — this is
        // what keeps invalidateSize() and a reopened modal from posting the
        // position that is already stored, and what makes unticking Inherit by
        // hand a change even when the centre has not moved.
        function stateKey(s) {
            return [inheriting() ? 1 : 0, s.lat.toFixed(6), s.lng.toFixed(6), s.zoom].join('|');
        }

        function setState(state, message) {
            if (!indicatorEl) return;
            indicatorEl.setAttribute('data-state', state);
            var label = indicatorEl.querySelector('.autosave-label');
            if (label) label.textContent = message;
        }

        function writeLabel(s) {
            if (!coordsEl) return;
            if (inheriting()) {
                coordsEl.textContent = labels.inheriting ||
                    'Inheriting the survey position — drag the map to give this section its own';
                return;
            }
            coordsEl.textContent = (labels.centre || 'Centre') + ' ' +
                s.lat.toFixed(5) + ', ' + s.lng.toFixed(5) +
                ' · ' + (labels.zoom || 'zoom') + ' ' + s.zoom;
        }

        // Returns null when the fields cannot be read. A save is then ABANDONED
        // rather than sent: extraFields() reads controls that live in the panel,
        // and once HTMX has swapped the panel away they are gone. Substituting a
        // default would post `use_geolocation=0` -- a choice the creator never
        // made -- and persist it. #192 dereferenced them unguarded and threw.
        function payload(s) {
            var extra;
            try {
                extra = typeof o.extraFields === 'function' ? o.extraFields() : (o.extraFields || {});
            } catch (err) {
                return null;
            }
            if (!extra) return null;
            var fd = new FormData();
            if (inherit) fd.append('clear_position', inheriting() ? '1' : '0');
            fd.append('lat', s.lat);
            fd.append('lng', s.lng);
            fd.append('zoom', s.zoom);
            Object.keys(extra).forEach(function (k) { fd.append(k, extra[k]); });
            return fd;
        }

        function save() {
            clearTimeout(timer);
            // The container leaving the document is the same event as the panel
            // being swapped; checking here means a caller that forgets to call
            // detach() still cannot fire against a detached DOM.
            if (detached || !document.body.contains(map.getContainer())) {
                detach();
                return;
            }
            if (inFlight) { queued = true; return; }
            var s = current();
            var body = payload(s);
            if (!body) return;
            inFlight = true;
            var key = stateKey(s);
            setState('saving', labels.saving || 'Saving…');
            fetch(o.url, {
                method: 'POST',
                headers: { 'X-CSRFToken': o.csrfToken || '' },
                body: body,
            }).then(function (resp) {
                if (!resp.ok) throw resp;
                lastKey = key;
                setState('saved', labels.saved || 'All changes saved');
                // survey_detail.html refreshes the Live preview on this, so
                // the creator sees the respondent map re-centre.
                document.body.dispatchEvent(new CustomEvent('sectionSaved', { detail: { mapPosition: true } }));
            }).catch(function () {
                setState('error', labels.error || 'Not saved — tap to retry');
            }).finally(function () {
                inFlight = false;
                if (queued) { queued = false; schedule(); }
            });
        }

        function schedule() {
            clearTimeout(timer);
            timer = setTimeout(save, DEBOUNCE_MS);
        }

        // Every settled move lands here.
        function sync() {
            var s = current();
            writeLabel(s);
            if (inheriting()) return;
            if (stateKey(s) === lastKey) return;
            schedule();
        }

        // "This view is the saved one" — nothing to write until the creator
        // moves. Used after a courtesy geolocation flight on a survey that has
        // no position yet: a move made on the creator's behalf is not a decision.
        function rebase() {
            clearTimeout(timer);
            lastKey = stateKey(current());
            writeLabel(current());
        }

        // A creator gesture. While Inherit is ticked it means "this section gets
        // its own position": untick, light the pin, and let the move that
        // follows save the centre. schedule() covers the gesture that moves
        // nothing (a wheel at max zoom) so the untick itself still lands.
        function touched() {
            if (!inheriting()) return;
            inherit.checkbox.checked = false;
            pin.classList.remove('is-inherit');
            writeLabel(current());
            schedule();
        }

        function applyInherit() {
            var on = inheriting();
            pin.classList.toggle('is-inherit', on);
            if (on) {
                writeLabel(current());
                // Save the cleared position now — a checkbox is a deliberate
                // act — then fly. The fly's moveend finds Inherit ticked and
                // writes nothing, so the default cannot come back as a position.
                save();
                map.flyTo([inherit.lat, inherit.lng], inherit.zoom, { animate: true, duration: 0.5 });
            } else {
                // Unticked by hand: the centre, wherever it is, is now this
                // section's own position. Honest, and the next drag refines.
                sync();
            }
        }

        mapOn('moveend', sync);
        mapOn('zoomend', sync);

        if (inherit && inherit.checkbox) {
            pin.classList.toggle('is-inherit', inheriting());
            on(inherit.checkbox, 'change', applyInherit);
            // The create page's list of gestures Leaflet cannot attribute to
            // the creator by itself: a programmatic setView/flyTo fires none.
            var mapEl = map.getContainer();
            mapOn('dragstart', touched);
            on(mapEl, 'wheel', touched, { passive: true });
            on(mapEl, 'dblclick', touched);
            on(mapEl, 'touchstart', function (e) {
                if (e.touches && e.touches.length > 1) touched();
            }, { passive: true });
            // Capture phase on purpose: Leaflet's zoom control stops click
            // propagation at itself (disableClickPropagation), so a bubbling
            // listener here would never see the +/- buttons.
            on(mapEl, 'click', function (e) {
                if (e.target.closest && e.target.closest('.leaflet-control-zoom')) touched();
            }, true);
        }

        (o.watch || []).forEach(function (el) {
            if (el) on(el, 'change', save);
        });

        // The indicator doubles as the retry control in the error state.
        if (indicatorEl) {
            on(indicatorEl, 'click', function () {
                if (indicatorEl.getAttribute('data-state') === 'error') save();
            });
        }

        if (o.locate) {
            var LocateControl = L.Control.extend({
                options: { position: 'topright' },
                onAdd: function () {
                    var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                    var link = L.DomUtil.create('a', '', container);
                    link.href = '#';
                    link.title = labels.myLocation || 'My location';
                    link.setAttribute('role', 'button');
                    link.setAttribute('aria-label', labels.myLocation || 'My location');
                    link.style.cssText = 'display:flex;align-items:center;justify-content:center;width:30px;height:30px;cursor:pointer;background:#fff;color:#374151;font-size:14px;';
                    L.DomUtil.create('i', 'fas fa-crosshairs', link);
                    L.DomEvent.on(link, 'click', function (e) {
                        L.DomEvent.preventDefault(e);
                        L.DomEvent.stopPropagation(e);
                        if (!navigator.geolocation) {
                            if (coordsEl) coordsEl.textContent = labels.noGeolocation || 'Geolocation is not available in this browser.';
                            return;
                        }
                        if (coordsEl) coordsEl.textContent = labels.locating || 'Locating you…';
                        navigator.geolocation.getCurrentPosition(function (pos) {
                            touched();
                            map.setView([pos.coords.latitude, pos.coords.longitude], 15); // moveend → sync
                        }, function () {
                            if (coordsEl) coordsEl.textContent = labels.locateFailed ||
                                "Couldn't get your location — search for a place or drag the map instead.";
                        }, { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 });
                    });
                    return container;
                }
            });
            map.addControl(new LocateControl());
        }

        // Stop everything. A pending save is dropped rather than fired at a DOM
        // that is no longer there; calling it twice is harmless, so a caller can
        // wire it to both a modal close and an HTMX teardown without guarding.
        function detach() {
            if (detached) return;
            detached = true;
            clearTimeout(timer);
            queued = false;
            teardown.splice(0).forEach(function (undo) { undo(); });
            if (pin.parentNode) pin.parentNode.removeChild(pin);
        }

        // Self-wiring teardown: htmx fires this on every element it is about to
        // remove, so a picker inside a swapped fragment stops itself without the
        // template having to remember. save() checks document containment too --
        // the two are independent on purpose, because a teardown hook that
        // silently stops matching is exactly how this class of bug returns.
        on(map.getContainer(), 'htmx:beforeCleanupElement', detach);

        // The view the page opened with is the stored one.
        rebase();

        return { save: save, sync: sync, touched: touched, rebase: rebase, detach: detach };
    }

    window.MapPositionPicker = { attach: attach };
}(window, document));
