/* The photographed page beside the entry form (change paper-photo-entry, #495).
 *
 * `#paper-pane` is rendered inside the panel by _paper_pane.html on every
 * section of a sheet session. This script moves it onto `#paper-stage` (created
 * once beside #map), wires the page switcher, zoom and rotation, marks the
 * doubtful and blank fields from #section-data, and counts them in the entry
 * bar. Idempotent per swap: HTMX replaces the panel, the pane comes with it,
 * and `init` runs again from htmx:afterSettle. Nothing here writes markup:
 * every node is created with the DOM API and filled with textContent. */
(function () {
    'use strict';
    var state = { zoom: 1, rotation: 0 };

    function clear(el) {
        while (el.firstChild) el.removeChild(el.firstChild);
    }

    function stage() {
        var el = document.getElementById('paper-stage');
        if (!el) {
            el = document.createElement('div');
            el.id = 'paper-stage';
            var map = document.getElementById('map');
            (map && map.parentNode ? map.parentNode : document.body).insertBefore(el, map ? map.nextSibling : null);
        }
        return el;
    }

    function init() {
        var pane = document.getElementById('paper-pane');
        var data = document.getElementById('section-data');
        if (!pane || !data) {
            document.body.classList.remove('paper-review', 'paper-show-map');
            return;
        }
        var host = stage();
        clear(host);
        host.appendChild(pane);
        document.body.classList.add('paper-review');
        document.body.classList.remove('paper-show-map');

        var pages = [];
        try { pages = JSON.parse(pane.dataset.paperPages || '[]'); } catch (e) { pages = []; }
        var current = parseInt(pane.dataset.paperCurrent, 10) || (pages[0] && pages[0].id);
        var img = pane.querySelector('.paper-pane__img');
        var strip = pane.querySelector('.paper-pane__pages');

        function applyTransform() {
            if (!img) return;
            // Rotating around the top-left corner pushes the picture out of the
            // viewport; shift it back by its own size.
            var w = img.clientWidth, h = img.clientHeight;
            var shift = { 0: '', 90: 'translate(' + h + 'px, 0)', 180: 'translate(' + w + 'px, ' + h + 'px)', 270: 'translate(0, ' + w + 'px)' }[state.rotation] || '';
            img.style.transform = shift + ' rotate(' + state.rotation + 'deg) scale(' + state.zoom + ')';
        }
        function show(id) {
            current = id;
            var page = pages.filter(function (p) { return p.id === id; })[0];
            if (img && page) img.src = page.url;
            if (strip) {
                Array.prototype.forEach.call(strip.querySelectorAll('button'), function (b) {
                    b.classList.toggle('is-active', parseInt(b.dataset.page, 10) === id);
                });
            }
            applyTransform();
        }
        if (strip) {
            clear(strip);
            pages.forEach(function (p) {
                var b = document.createElement('button');
                b.type = 'button';
                b.className = 'paper-pane__btn';
                b.dataset.page = p.id;
                b.textContent = p.number ? String(p.number) : '?';
                b.addEventListener('click', function () { show(p.id); });
                strip.appendChild(b);
            });
        }
        Array.prototype.forEach.call(pane.querySelectorAll('[data-paper-zoom]'), function (b) {
            b.addEventListener('click', function () {
                state.zoom = b.dataset.paperZoom === '+' ? Math.min(4, state.zoom * 1.25) : Math.max(0.5, state.zoom / 1.25);
                applyTransform();
            });
        });
        var rotate = pane.querySelector('[data-paper-rotate]');
        if (rotate) rotate.addEventListener('click', function () { state.rotation = (state.rotation + 90) % 360; applyTransform(); });
        var toggle = pane.querySelector('[data-paper-toggle]');
        if (toggle) toggle.addEventListener('click', function () {
            var showMap = document.body.classList.toggle('paper-show-map');
            toggle.classList.toggle('is-active', showMap);
            if (showMap && window.map && typeof window.map.invalidateSize === 'function') {
                setTimeout(function () { window.map.invalidateSize(); }, 50);
            }
        });
        var viewport = pane.querySelector('.paper-pane__viewport');
        if (viewport) {
            viewport.addEventListener('wheel', function (e) {
                if (!e.ctrlKey) return;
                e.preventDefault();
                state.zoom = e.deltaY < 0 ? Math.min(4, state.zoom * 1.1) : Math.max(0.5, state.zoom / 1.1);
                applyTransform();
            }, { passive: false });
        }
        if (img) img.addEventListener('load', applyTransform);
        if (current) show(current);

        markFields(data);
    }

    function markFields(data) {
        var doubtful = (data.dataset.paperDoubtful || '').split(',').filter(Boolean);
        var blank = (data.dataset.paperBlank || '').split(',').filter(Boolean);
        var note = data.dataset.paperNote || 'Check this against the photo';
        doubtful.forEach(function (code) {
            var card = document.querySelector('.question-card[data-field-name="' + code + '"]');
            if (card) { card.classList.add('paper-doubtful'); card.setAttribute('data-paper-note', note); }
        });
        blank.forEach(function (code) {
            var card = document.querySelector('.question-card[data-field-name="' + code + '"]');
            if (card && !card.classList.contains('paper-doubtful')) card.classList.add('paper-blank');
        });
        var counter = document.querySelector('[data-paper-check-count]');
        if (counter) {
            if (doubtful.length) {
                var tmpl = counter.dataset.paperCheckLabel || '{count} fields to check';
                counter.textContent = '· ' + tmpl.replace('{count}', String(doubtful.length));
                counter.hidden = false;
            } else {
                counter.hidden = true;
            }
        }
    }

    document.addEventListener('DOMContentLoaded', init);
    document.body.addEventListener('htmx:afterSettle', function () { setTimeout(init, 0); });
})();
