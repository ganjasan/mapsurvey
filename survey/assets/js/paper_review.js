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
        if (followCleanup) followCleanup();
        var pane = document.getElementById('paper-pane');
        var data = document.getElementById('section-data');
        if (!pane || !data) {
            var head = document.getElementById('paper-head');
            if (head) head.parentNode.removeChild(head);
            document.body.classList.remove('paper-review', 'paper-show-map', 'paper-head-on');
            return;
        }
        var host = stage();
        clear(host);
        host.appendChild(pane);
        document.body.classList.add('paper-review');
        document.body.classList.remove('paper-show-map');
        // Photo left, form right: on a map section the panel moves to the right
        // (the section layout option), the stage mirrors with it in CSS.
        if (pane.dataset.paperLayout !== 'form') document.body.classList.add('panel-right');

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
            if (follow) follow.reposition();
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
        var follow = viewport && img ? makeFollow(viewport, img, function () {
            var page = pages.filter(function (p) { return p.id === current; })[0];
            return (page && page.boxes) || {};
        }) : null;
        if (img) img.addEventListener('load', applyTransform);
        if (current) show(current);

        wireAttach(pane.querySelector('.paper-attach'));
        markFields(data);
        buildHead(pane, data);
    }

    // The form leads, the photo follows (owner, 2026-10-31). The question the
    // operator is on — the focused field, else the card crossing a line a third
    // down the form's scroll area — scrolls the photo to where the model said
    // that question is (`boxes`: [ymin, xmin, ymax, xmax] in 0..1000 of the
    // photo) and outlines it. Without a box (a page read before boxes existed,
    // or a rotated photo) the photo keeps the form's scroll proportion instead.
    // One direction only: scrolling the photo by hand moves nothing in the form.
    var followCleanup = null;

    function makeFollow(viewport, img, boxesOf) {
        if (followCleanup) followCleanup();
        var frame = document.createElement('div');
        frame.className = 'paper-pane__box';
        frame.hidden = true;
        viewport.appendChild(frame);
        var activeCode = null, ticking = false;
        var panel = document.getElementById('info_page');

        function cards() {
            return Array.prototype.slice.call(document.querySelectorAll('#section-data .question-card[data-field-name]'));
        }
        function geometry(box) {
            var w = img.clientWidth * state.zoom, h = img.clientHeight * state.zoom;
            return { top: box[0] / 1000 * h, left: box[1] / 1000 * w,
                     height: (box[2] - box[0]) / 1000 * h, width: (box[3] - box[1]) / 1000 * w };
        }
        function placeFrame(box) {
            if (!box || state.rotation) { frame.hidden = true; return null; }
            var g = geometry(box);
            frame.style.top = (img.offsetTop + g.top - 4) + 'px';
            frame.style.left = (img.offsetLeft + g.left - 4) + 'px';
            frame.style.width = (g.width + 8) + 'px';
            frame.style.height = (g.height + 8) + 'px';
            frame.hidden = false;
            return g;
        }
        function scrollArea() {
            // A map section scrolls inside the panel; a form section scrolls the page.
            if (panel && panel.scrollHeight > panel.clientHeight + 1 && getComputedStyle(panel).overflowY !== 'visible') {
                var r = panel.getBoundingClientRect();
                return { top: r.top, height: panel.clientHeight, fraction: panel.scrollTop / Math.max(1, panel.scrollHeight - panel.clientHeight) };
            }
            var se = document.scrollingElement || document.documentElement;
            var head = document.getElementById('paper-head');
            var top = head ? head.offsetHeight : 0;
            return { top: top, height: window.innerHeight - top, fraction: se.scrollTop / Math.max(1, se.scrollHeight - se.clientHeight) };
        }
        function codeInView() {
            var focused = document.activeElement && document.activeElement.closest &&
                document.activeElement.closest('#section-data .question-card[data-field-name]');
            if (focused) return focused.dataset.fieldName;
            var area = scrollArea(), line = area.top + area.height / 3, best = null, bestDist = Infinity;
            cards().forEach(function (card) {
                var r = card.getBoundingClientRect();
                var dist = line < r.top ? r.top - line : (line > r.bottom ? line - r.bottom : 0);
                if (dist < bestDist) { bestDist = dist; best = card; }
            });
            return best ? best.dataset.fieldName : null;
        }
        function update(force) {
            ticking = false;
            var code = codeInView();
            var boxes = boxesOf();
            var box = code ? boxes[code] : null;
            if (!force && code === activeCode && box) return;
            activeCode = code;
            cards().forEach(function (card) { card.classList.toggle('paper-active', card.dataset.fieldName === code); });
            var g = placeFrame(box);
            if (g) {
                var target = img.offsetTop + g.top - Math.max(16, (viewport.clientHeight - g.height) / 3);
                viewport.scrollTo({ top: Math.max(0, target), left: Math.max(0, img.offsetLeft + g.left - 16), behavior: force ? 'auto' : 'smooth' });
            } else {
                var area = scrollArea();
                viewport.scrollTop = area.fraction * Math.max(0, viewport.scrollHeight - viewport.clientHeight);
            }
        }
        function schedule() {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(function () { update(false); });
        }
        var onFocus = function () { schedule(); };
        window.addEventListener('scroll', schedule, { passive: true });
        if (panel) panel.addEventListener('scroll', schedule, { passive: true });
        document.addEventListener('focusin', onFocus);
        followCleanup = function () {
            window.removeEventListener('scroll', schedule);
            if (panel) panel.removeEventListener('scroll', schedule);
            document.removeEventListener('focusin', onFocus);
            if (frame.parentNode) frame.parentNode.removeChild(frame);
            followCleanup = null;
        };
        img.addEventListener('load', function () { update(true); });
        if (img.complete && img.naturalWidth) setTimeout(function () { update(true); }, 0);
        var pinned = null;   // a box the page asked for (a marks-table row); released by the next form move
        var api = {
            // zoom or rotation changed: the same question, a new place on screen
            reposition: function () { if (pinned) api.focusBox(pinned); else update(true); },
            // The map page's marks table: show THIS mark on the photo, whatever the form says.
            focusBox: function (box) {
                pinned = box || null;
                activeCode = null;
                var g = placeFrame(box);
                if (!g) return;
                var target = img.offsetTop + g.top - Math.max(16, (viewport.clientHeight - g.height) / 3);
                viewport.scrollTo({ top: Math.max(0, target), left: Math.max(0, img.offsetLeft + g.left - 16), behavior: 'smooth' });
            },
        };
        var release = function () { pinned = null; };
        window.addEventListener('scroll', release, { passive: true });
        if (panel) panel.addEventListener('scroll', release, { passive: true });
        window.PaperReview = api;
        return api;
    }

    // One header over the photo and the form (owner, 2026-10-31): where you are,
    // the pages, the photo tools and Stop, in one row across both columns. The
    // nodes are MOVED out of the entry bar, the stepper and the pane bar (their
    // listeners and the stepper's form= attribute travel with them), so a swap
    // that brings new ones simply rebuilds the row. Desktop only: on a phone the
    // photo sits above the form and the original bars stay where they are.
    function buildHead(pane, data) {
        var old = document.getElementById('paper-head');
        if (old) old.parentNode.removeChild(old);
        document.body.classList.remove('paper-head-on');
        if (!window.matchMedia || !window.matchMedia('(min-width: 769px)').matches) return;

        var head = document.createElement('div');
        head.id = 'paper-head';
        head.className = 'paper-head';

        var where = document.createElement('div');
        where.className = 'paper-head__where';
        if (pane.dataset.paperHomeUrl) {
            var back = document.createElement('a');
            back.className = 'paper-head__back';
            back.href = pane.dataset.paperHomeUrl;
            back.textContent = '← ' + (pane.dataset.paperHomeLabel || '');
            where.appendChild(back);
        }
        var meta = document.createElement('span');
        meta.className = 'paper-head__meta';
        meta.textContent = pane.dataset.paperMeta || '';
        where.appendChild(meta);
        var check = data.querySelector('[data-paper-check-count]');
        if (check) where.appendChild(check);
        head.appendChild(where);

        var middle = document.createElement('div');
        middle.className = 'paper-head__pages';
        var stepper = data.querySelector('.paper-stepper');
        var strip = pane.querySelector('.paper-pane__pages');
        if (stepper) middle.appendChild(stepper);
        else if (strip) middle.appendChild(strip);   // the section flow of an old form: the photo switcher
        head.appendChild(middle);

        var tools = document.createElement('div');
        tools.className = 'paper-head__tools';
        var paneTools = pane.querySelector('.paper-pane__tools');
        if (paneTools) tools.appendChild(paneTools);
        var stop = data.querySelector('.operator-entry-bar__exit');
        if (stop) { stop.classList.add('paper-head__stop'); tools.appendChild(stop); }
        head.appendChild(tools);

        document.body.appendChild(head);
        document.body.classList.add('paper-head-on');
    }

    // A page that was never photographed: the operator attaches it here. The
    // file goes to the batch's upload endpoint with the sheet and page number,
    // the page is read in the worker, and this page reloads with the fields
    // filled once the status endpoint says it is recognised.
    function wireAttach(box) {
        if (!box || box.dataset.wired) return;
        box.dataset.wired = '1';
        var camera = box.querySelector('.paper-attach__camera');
        var file = box.querySelector('.paper-attach__file');
        var state = box.querySelector('.paper-attach__state');
        var shoot = box.querySelector('.paper-attach__shoot');
        var pick = box.querySelector('.paper-attach__pick');
        function say(text) { if (state) { state.textContent = text; state.hidden = !text; } }
        function poll() {
            fetch(box.dataset.paperStatusUrl, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (s) {
                    if (s.state === 'recognised' || s.state === 'unrecognised') { window.location.reload(); return; }
                    // Another copy's page (or this copy's other page): it went where its code says.
                    if (s.state === 'failed' || s.state === 'set_aside') { say(s.error || box.dataset.msgFailed || 'Failed'); return; }
                    setTimeout(poll, 2000);
                })
                .catch(function () { setTimeout(poll, 3000); });
        }
        function send(f) {
            if (!f) return;
            say(box.dataset.msgUploading || '…');
            var body = new FormData();
            body.append('file', f, f.name);
            body.append('sheet', box.dataset.paperSheet);
            body.append('page_number', box.dataset.paperNumber);
            fetch(box.dataset.paperAttachUrl, { method: 'POST', body: body, credentials: 'same-origin',
                                                headers: { 'X-CSRFToken': box.dataset.csrf } })
                .then(function (r) { if (!r.ok) throw new Error('upload'); say(box.dataset.msgReading || '…'); poll(); })
                .catch(function () { say(box.dataset.msgFailed || 'Upload failed'); });
        }
        if (shoot && camera) shoot.addEventListener('click', function () { camera.click(); });
        if (pick && file) pick.addEventListener('click', function () { file.click(); });
        if (camera) camera.addEventListener('change', function () { send(camera.files && camera.files[0]); camera.value = ''; });
        if (file) file.addEventListener('change', function () { send(file.files && file.files[0]); file.value = ''; });
    }

    function markFields(data) {
        var doubtful = (data.dataset.paperDoubtful || '').split(',').filter(Boolean);
        var blank = (data.dataset.paperBlank || '').split(',').filter(Boolean);
        var note = data.dataset.paperNote || 'Check this against the photo';
        var actionLabel = data.dataset.paperCheckAction || 'Mark as checked';
        var checkedLabel = data.dataset.paperCheckedLabel || 'Checked';
        // What the operator has already checked on this page (owner, 2026-11-02: a
        // flagged field must be markable as fixed): browser-side, per page URL.
        var key = 'msPaperChecked:' + location.pathname;
        var checked = {};
        try { (JSON.parse(localStorage.getItem(key) || '[]')).forEach(function (c) { checked[c] = true; }); } catch (e) { /* no storage */ }
        function save() {
            try { localStorage.setItem(key, JSON.stringify(Object.keys(checked))); } catch (e) { /* no storage */ }
        }
        var counter = document.querySelector('[data-paper-check-count]');
        function count() {
            if (!counter) return;
            var left = doubtful.filter(function (c) { return !checked[c]; }).length;
            if (left) {
                var tmpl = left === 1
                    ? (counter.dataset.paperCheckLabelOne || '{count} field to check')
                    : (counter.dataset.paperCheckLabel || '{count} fields to check');
                counter.textContent = tmpl.replace('{count}', String(left));
                counter.hidden = false;
            } else {
                counter.hidden = true;
            }
        }
        function paint(host, code, btn) {
            var done = !!checked[code];
            host.classList.toggle('paper-checked', done);
            btn.textContent = '';
            var text = document.createElement('span');
            text.textContent = done ? checkedLabel : note;
            btn.appendChild(text);
            var action = document.createElement('span');
            action.className = 'paper-check__action';
            action.textContent = done ? '✓' : actionLabel;
            btn.appendChild(action);
            btn.setAttribute('aria-pressed', done ? 'true' : 'false');
        }
        doubtful.forEach(function (code) {
            var card = document.querySelector('.question-card[data-field-name="' + code + '"]');
            var block = document.querySelector('.paper-marks__q[data-marks-question="' + code + '"]');
            var host = card || block;
            if (!host) return;
            host.classList.add(card ? 'paper-doubtful' : 'paper-marks__q--doubt');
            var btn = host.querySelector('.paper-check');
            if (!btn) {
                btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'paper-check';
                if (card) {
                    host.insertBefore(btn, host.firstChild);
                } else {
                    var old = host.querySelector('.paper-marks__doubt');
                    if (old) old.remove();
                    var title = host.querySelector('.paper-marks__title') || host;
                    title.appendChild(btn);
                }
                btn.addEventListener('click', function () {
                    if (checked[code]) delete checked[code]; else checked[code] = true;
                    save();
                    paint(host, code, btn);
                    count();
                });
            }
            paint(host, code, btn);
        });
        blank.forEach(function (code) {
            var card = document.querySelector('.question-card[data-field-name="' + code + '"]');
            if (card && !card.classList.contains('paper-doubtful')) card.classList.add('paper-blank');
        });
        count();
    }

    document.addEventListener('DOMContentLoaded', init);
    document.body.addEventListener('htmx:afterSettle', function () { setTimeout(init, 0); });
})();
