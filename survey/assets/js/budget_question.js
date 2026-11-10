/* Budget questions (change budget-question, spec budget-question).
 *
 * `[data-budget]` — a `budget` question: Split (amount inputs per item, named
 * `<code>__<item>`) or Projects (checkboxes under the question's name). The
 * inputs ARE the answer; this file adds steppers, sliders, the live remainder,
 * disables what does not fit, and writes the hint that tells the respondent
 * why Next is blocked.
 *
 * `[data-budget-group]` — a budget group: a total over the ordinary map
 * questions inside it, each with a price (per mark, per metre, per m²). The
 * page's own draw paths place the marks; this file sums what they cost
 * (refreshGroups, called by refreshGeoQuestionUI), blocks a draw button whose
 * next mark could not fit, and refuses a drawn line or area that costs more
 * than what is left (admit, called from draw:created).
 *
 * Nothing here is trusted: survey/budget.py re-checks every POST.
 * Initialised on load and after every htmx swap.
 */
(function () {
    'use strict';

    var T = {
        left: '{left} left',
        allIn: '✓ all allocated',
        over: '{over} over the budget',
        needAll: 'Allocate the whole {total} — {left} is still unallocated.',
        needOne: 'Give at least one item an amount.',
        needMin: 'Pick at least {n}.',
        tooDear: '{over} over what is left.',
        capReached: 'You placed the most allowed.',
        noCost: "No cost set — can't be picked.",
        markTooDear: 'This mark would cost {cost}, but only {left} is left.',
        leftAfter: '{left} left after it',
    };
    // Translations come from the page's i18n object (respondent catalogs,
    // i18n_extras.i18n_json → `budget`), English otherwise.
    function t(key, vars) {
        var page = window.i18n && window.i18n.budget;
        var src = (page && page[key]) || T[key];
        return src.replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] !== undefined ? vars[k] : m; });
    }

    function num(v) {
        var n = parseFloat(String(v).replace(/[\s,]/g, ''));
        return isFinite(n) ? n : 0;
    }

    function trim(n) {
        if (Math.round(n) === n) return String(n);
        return n.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
    }

    // Mirrors survey/budget.py::format_amount — keep the two in step.
    function fmt(amount, cfg) {
        if (cfg.unit === 'percent') return trim(amount) + '%';
        var a = Math.abs(amount), sign = amount < 0 ? '-' : '', body;
        if (a >= 1e6) body = trim(a / 1e6) + 'M';
        else if (a >= 1e4) body = trim(a / 1e3) + 'k';
        else body = Math.round(a).toLocaleString('en-GB').replace(/,/g, '\u202f');   // whole units: a price per metre gives fractions
        if (cfg.unit === 'points') return sign + body + ' pts';
        return sign + (cfg.symbol || '') + body;
    }

    function roundStep(v, step) {
        if (!step) return v;
        var r = Math.round(v / step) * step;
        return Math.round(r * 1e6) / 1e6;
    }

    function config(el) {
        try { return JSON.parse(el.getAttribute('data-budget-config') || '{}'); } catch (e) { return {}; }
    }

    // Items without a colour take turns on this palette, so the bar reads
    // even when the creator never picked one.
    var PALETTE = ['#4f46e5', '#0891b2', '#16a34a', '#ca8a04', '#db2777', '#9333ea', '#ea580c', '#64748b'];

    function colorOf(cfg, key, index) {
        var c = cfg.colors && cfg.colors[key];
        return c || PALETTE[index % PALETTE.length];
    }

    // `segments`: [{key, amount}] in item order — the bar is stacked in the
    // items' colours so the respondent sees what went where (owner, 2026-11-10).
    function paintBar(block, spent, total, segments) {
        var bar = block.querySelector('[data-budget-bar]');
        if (!bar) return;
        var cfg = config(block);
        var left = total - spent;
        var track = bar.querySelector('[data-budget-track]');
        if (track && segments) {
            while (track.firstChild) track.removeChild(track.firstChild);
            segments.forEach(function (seg, i) {
                if (!(seg.amount > 0)) return;
                var piece = document.createElement('i');
                piece.style.width = Math.max(0, Math.min(100, total ? seg.amount / total * 100 : 0)) + '%';
                piece.style.background = colorOf(cfg, seg.key, i);
                piece.title = seg.title || seg.key;
                track.appendChild(piece);
            });
        }
        bar.querySelector('[data-budget-spent]').textContent = fmt(spent, cfg);
        var leftEl = bar.querySelector('[data-budget-left]');
        leftEl.classList.remove('is-ok', 'is-over');
        if (left < 0) { leftEl.textContent = t('over', { over: fmt(-left, cfg) }); leftEl.classList.add('is-over'); }
        else if (left === 0 && cfg.mode === 'split') { leftEl.textContent = t('allIn'); leftEl.classList.add('is-ok'); }
        else leftEl.textContent = t('left', { left: fmt(left, cfg) });
        if (!segments) {
            var fill = bar.querySelector('[data-budget-track] > i');
            if (fill) fill.style.width = Math.max(0, Math.min(100, total ? spent / total * 100 : 0)) + '%';
        }
        track.classList.toggle('is-over', left < 0);
    }

    // ── `budget`: Split and Projects ────────────────────────────────────────

    function splitState(block) {
        var cfg = config(block), spent = 0;
        block.querySelectorAll('.budget-amount').forEach(function (inp) { spent += num(inp.value); });
        return { cfg: cfg, spent: Math.round(spent * 1e6) / 1e6, left: cfg.total - spent };
    }

    function refreshSplit(block) {
        var s = splitState(block);
        paintBar(block, s.spent, s.cfg.total, Array.prototype.map.call(block.querySelectorAll('.budget-item'), function (row) {
            return { key: row.getAttribute('data-budget-item'), amount: num(row.querySelector('.budget-amount').value),
                     title: (row.querySelector('.budget-item__name') || {}).textContent };
        }));
        block.querySelectorAll('.budget-item').forEach(function (row) {
            var inp = row.querySelector('.budget-amount');
            var v = num(inp.value);
            var slider = row.querySelector('.budget-slider');
            if (slider) {
                slider.value = v;
                // A slider never runs past what this item could still take.
                slider.max = s.cfg.total;
            }
            var inc = row.querySelector('[data-budget-inc]');
            if (inc) inc.disabled = s.left < s.cfg.step - 1e-9;
            var dec = row.querySelector('[data-budget-dec]');
            if (dec) dec.disabled = v <= 0;
            var pct = row.querySelector('[data-budget-pct]');
            if (pct && !pct.hidden) pct.textContent = Math.round(s.cfg.total ? v / s.cfg.total * 100 : 0) + '%';
        });
        var spread = block.querySelector('[data-budget-spread]');
        if (spread) spread.disabled = s.left <= 0;
        block.querySelector('[data-budget-hint]').textContent = '';
    }

    function setAmount(block, row, value) {
        var cfg = config(block);
        var inp = row.querySelector('.budget-amount');
        var others = splitState(block).spent - num(inp.value);
        var v = Math.max(0, roundStep(value, cfg.step));
        // Never past the budget: the control stops at what is left.
        var room = cfg.total - others;
        if (v > room) v = Math.max(0, Math.floor(room / cfg.step + 1e-9) * cfg.step);
        inp.value = Math.round(v * 1e6) / 1e6;
        refreshSplit(block);
    }

    function spreadRest(block) {
        var cfg = config(block);
        var rows = Array.prototype.slice.call(block.querySelectorAll('.budget-item:not([data-budget-off])'));
        if (!rows.length) return;
        var left = splitState(block).left;
        var steps = Math.floor(left / cfg.step + 1e-9), i = 0;
        while (steps > 0) {
            var inp = rows[i % rows.length].querySelector('.budget-amount');
            inp.value = Math.round((num(inp.value) + cfg.step) * 1e6) / 1e6;
            steps--; i++;
        }
        refreshSplit(block);
    }

    function refreshProjects(block) {
        var cfg = config(block), spent = 0;
        var rows = block.querySelectorAll('.budget-proj');
        rows.forEach(function (row) {
            var cb = row.querySelector('input[type="checkbox"]');
            if (cb.checked) spent += num(row.getAttribute('data-budget-cost'));
        });
        var left = cfg.total - spent;
        var segments = [];
        rows.forEach(function (row) {
            var cb = row.querySelector('input[type="checkbox"]');
            if (cb.checked) segments.push({ key: row.getAttribute('data-budget-item'), amount: num(row.getAttribute('data-budget-cost')),
                                            title: (row.querySelector('.budget-proj__name') || {}).textContent });
            var why = row.querySelector('[data-budget-why]');
            row.classList.toggle('is-in', cb.checked);
            if (row.hasAttribute('data-budget-off')) { cb.disabled = true; why.textContent = t('noCost'); return; }
            var cost = num(row.getAttribute('data-budget-cost'));
            var cant = !cb.checked && cost > left;
            cb.disabled = cant;
            row.classList.toggle('is-cant', cant);
            why.textContent = cant ? t('tooDear', { over: fmt(cost - left, cfg) }) : '';
        });
        paintBar(block, spent, cfg.total, segments);
        block.querySelector('[data-budget-hint]').textContent = '';
    }

    function initBudget(block) {
        if (block.dataset.budgetReady === '1') return;
        block.dataset.budgetReady = '1';
        var cfg = config(block);
        if (cfg.mode === 'split') {
            block.addEventListener('click', function (e) {
                var btn = e.target.closest('[data-budget-inc], [data-budget-dec]');
                if (btn) {
                    var row = btn.closest('.budget-item');
                    var inp = row.querySelector('.budget-amount');
                    setAmount(block, row, num(inp.value) + (btn.hasAttribute('data-budget-inc') ? cfg.step : -cfg.step));
                    return;
                }
                if (e.target.closest('[data-budget-spread]')) spreadRest(block);
            });
            block.addEventListener('input', function (e) {
                if (e.target.classList.contains('budget-slider')) {
                    setAmount(block, e.target.closest('.budget-item'), num(e.target.value));
                }
            });
            block.addEventListener('change', function (e) {
                if (e.target.classList.contains('budget-amount')) {
                    setAmount(block, e.target.closest('.budget-item'), num(e.target.value));
                }
            });
            refreshSplit(block);
        } else {
            block.addEventListener('change', function (e) {
                if (e.target.matches('input[type="checkbox"]')) refreshProjects(block);
            });
            refreshProjects(block);
        }
    }

    // ── Budget groups: a total over priced map questions ─────────────────────
    // `[data-budget-group]` sits in the group's header; its config carries the
    // total and the member questions' prices. The marks are the page's own
    // `editableLayers`, read through the `layersFor` the page hands over.

    function groupBlocks() {
        return Array.prototype.slice.call(document.querySelectorAll('[data-budget-group]'));
    }

    function latlngsOf(layer) {
        if (layer instanceof L.Marker) return [layer.getLatLng()];
        if (layer.getLatLngs) {
            var ll = layer.getLatLngs();
            // A polygon's rings nest one level; take the outer ring.
            while (ll.length && Array.isArray(ll[0])) ll = ll[0];
            return ll;
        }
        if (layer._dots) return layer._dots.map(function (d) { return L.latLng(d[0], d[1]); });
        return [];
    }

    // Measure the way survey/budget.py::measure does — close enough for a park.
    function measureOf(layer, per) {
        if (per === 'feature') return 1;
        var pts = latlngsOf(layer);
        if (per === 'length') {
            var m = 0;
            for (var i = 1; i < pts.length; i++) m += pts[i - 1].distanceTo(pts[i]);
            return m;
        }
        if (per === 'area') {
            if (window.L && L.SprayLayer && layer instanceof L.SprayLayer) {
                // Convex hull of the cloud, as the server does.
                pts = hull(pts);
            }
            return pts.length >= 3 && L.GeometryUtil && L.GeometryUtil.geodesicArea ? L.GeometryUtil.geodesicArea(pts) : 0;
        }
        return 0;
    }

    function hull(points) {
        var p = points.map(function (ll) { return [ll.lng, ll.lat]; })
            .sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
        if (p.length < 3) return points;
        function cross(o, a, b) { return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]); }
        var lower = [], upper = [];
        p.forEach(function (pt) {
            while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0) lower.pop();
            lower.push(pt);
        });
        p.slice().reverse().forEach(function (pt) {
            while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0) upper.pop();
            upper.push(pt);
        });
        return lower.slice(0, -1).concat(upper.slice(0, -1)).map(function (q) { return L.latLng(q[1], q[0]); });
    }

    function layerCost(layer, prices) {
        var qid = layer.feature && layer.feature.properties && layer.feature.properties.question_id;
        var price = prices[qid];
        return price ? price.amount * measureOf(layer, price.per) : 0;
    }

    function groupSpent(block, layersFor, segments) {
        var cfg = config(block), spent = 0;
        Object.keys(cfg.prices || {}).forEach(function (qid) {
            var mine = 0;
            layersFor(qid).forEach(function (l) { mine += layerCost(l, cfg.prices); });
            spent += mine;
            if (segments) segments.push({ key: qid, amount: mine, title: (cfg.titles || {})[qid] || qid });
        });
        return spent;
    }

    // Called by refreshGeoQuestionUI after every add/remove/edit — after it has
    // enabled the buttons and restored their subtitles, so what is written
    // here holds until the next refresh: repaint the bars and block the draw
    // buttons whose next mark could not fit.
    function refreshGroups(layersFor) {
        window.BudgetQuestion._layersFor = layersFor;
        groupBlocks().forEach(function (block) {
            var cfg = config(block);
            var segments = [];
            var spent = groupSpent(block, layersFor, segments);
            var left = cfg.total - spent;
            paintBar(block, spent, cfg.total, segments);
            Object.keys(cfg.prices || {}).forEach(function (qid) {
                var price = cfg.prices[qid];
                var btn = document.querySelector('button.drawbutton[name="' + qid + '"]');
                if (!btn || price.per !== 'feature') return;
                if (price.amount > left + 1e-9) {
                    btn.disabled = true;
                    var sub = btn.querySelector('.geo-question-subtitle');
                    if (sub) sub.textContent = t('tooDear', { over: fmt(price.amount - left, cfg) });
                }
            });
            var hint = block.querySelector('[data-budget-hint]');
            // Only the "over the budget" note is ours to clear; a refusal from
            // admit() stays until the next successful placement.
            if (left >= -1e-9 && hint.getAttribute('data-budget-hint-kind') === 'over') {
                hint.textContent = '';
                hint.removeAttribute('data-budget-hint-kind');
            }
        });
        // The chip follows the armed question (window.currentQ is the page's).
        var armed = window.currentQ;
        var busy = !!window.currentDrawFeature
            || (document.getElementById('crosshair-overlay') || {}).style && document.getElementById('crosshair-overlay').style.display === 'flex';
        showPlacing(busy ? armed : null, null);
    }

    // ── While placing: the panel (and its bar) is hidden, so a chip above the
    // draw bar says what this mark costs and what is left (owner, 2026-11-10).
    function chip() {
        var el = document.getElementById('budget-draw-chip');
        if (!el) {
            el = document.createElement('div');
            el.id = 'budget-draw-chip';
            el.setAttribute('role', 'status');
            el.setAttribute('aria-live', 'polite');
            document.body.appendChild(el);
        }
        return el;
    }

    function blockFor(qid) {
        return groupBlocks().filter(function (b) { return (config(b).prices || {})[qid]; })[0] || null;
    }

    // Shown whenever a priced question is armed (crosshair, tap-to-place, a
    // draw in progress); refreshGroups calls it, so arming and finishing both
    // refresh it. `draft` is the shape being drawn, when there is one.
    function showPlacing(qid, draft) {
        var el = chip();
        var block = qid && blockFor(qid);
        if (!block) { el.hidden = true; return; }
        var cfg = config(block);
        var price = cfg.prices[qid];
        var left = cfg.total - groupSpent(block, window.BudgetQuestion._layersFor || function () { return []; });
        var name = (cfg.titles || {})[qid] || qid;
        var cost, size = '';
        if (draft && draft.pts && price.per !== 'feature') {
            var m = measureOfPoints(draft.pts, price.per, draft.polygon);
            cost = price.amount * m;
            size = price.per === 'length' ? Math.round(m).toLocaleString('en-GB').replace(/,/g, '\u202f') + ' m'
                                          : Math.round(m).toLocaleString('en-GB').replace(/,/g, '\u202f') + ' m²';
        } else {
            cost = price.per === 'feature' ? price.amount : 0;
        }
        var after = left - cost;
        while (el.firstChild) el.removeChild(el.firstChild);
        var sw = document.createElement('i');
        sw.style.background = colorOf(cfg, qid, 0);
        el.appendChild(sw);
        var txt = document.createElement('span');
        txt.textContent = name + (size ? ' · ' + size : '') + ' · ' + fmt(cost, cfg)
            + ' · ' + (after < -1e-9 ? t('over', { over: fmt(-after, cfg) }) : t('leftAfter', { left: fmt(after, cfg) }));
        el.appendChild(txt);
        el.classList.toggle('is-over', after < -1e-9);
        el.hidden = false;
    }

    function measureOfPoints(pts, per, polygon) {
        if (per === 'length') {
            var m = 0;
            for (var i = 1; i < pts.length; i++) m += pts[i - 1].distanceTo(pts[i]);
            return m;
        }
        return pts.length >= 3 && L.GeometryUtil && L.GeometryUtil.geodesicArea ? L.GeometryUtil.geodesicArea(pts) : 0;
    }

    // The page calls this on every vertex and mouse move while a Leaflet.draw
    // handler is active: the shape so far plus the rubber-band point.
    function drawing(handler, qid) {
        if (!handler || !qid) return;
        var pts = [];
        if (handler._poly && handler._poly.getLatLngs) pts = handler._poly.getLatLngs().slice();
        if (handler._currentLatLng) pts.push(handler._currentLatLng);
        showPlacing(qid, { pts: pts, polygon: !!(handler instanceof L.Draw.Polygon) });
    }

    // Called from draw:created before the mark is kept: a line or an area is
    // priced by its size, so only now is its cost known. False = do not keep it.
    function admit(layer, qid) {
        var block = groupBlocks().filter(function (b) { return (config(b).prices || {})[qid]; })[0];
        if (!block) return true;
        var cfg = config(block);
        var layersFor = window.BudgetQuestion._layersFor || function () { return []; };
        var cost = layerCost(layer, cfg.prices);
        var left = cfg.total - groupSpent(block, layersFor);
        var hint = block.querySelector('[data-budget-hint]');
        if (cost <= left + 1e-9) { hint.textContent = ''; hint.removeAttribute('data-budget-hint-kind'); return true; }
        hint.textContent = t('markTooDear', { cost: fmt(cost, cfg), left: fmt(Math.max(0, left), cfg) });
        hint.setAttribute('data-budget-hint-kind', 'refused');
        try { block.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (e) {}
        return false;
    }

    // Editing may stretch a priced line past the budget; Next then says so
    // (the server would drop the mark that no longer fits).
    function firstInvalidGroup(form) {
        var first = null;
        groupBlocks().forEach(function (block) {
            if (!form.contains(block)) return;
            var cfg = config(block);
            var left = cfg.total - groupSpent(block, window.BudgetQuestion._layersFor || function () { return []; });
            if (left < -1e-9) {
                var hint = block.querySelector('[data-budget-hint]');
                hint.textContent = t('over', { over: fmt(-left, cfg) });
                hint.setAttribute('data-budget-hint-kind', 'over');
                if (!first) first = block;
            }
        });
        return first;
    }

    // Next: what each budget block still needs, written under the block; the
    // first such block is returned for the page to scroll to.
    function firstInvalid(form) {
        var first = null;
        form.querySelectorAll('[data-budget]').forEach(function (block) {
            var card = block.closest('.question-card');
            if (card && (card.hidden || (window.ConditionalVisibility && ConditionalVisibility.isHidden(card)))) return;
            var cfg = config(block), msg = '';
            var required = card && card.getAttribute('data-required') === 'true';
            if (cfg.mode === 'split') {
                var s = splitState(block);
                var touched = s.spent > 0;
                if (s.left < 0) msg = t('over', { over: fmt(-s.left, cfg) });
                else if (cfg.rule === 'all' && (touched || required) && s.left > 0)
                    msg = t('needAll', { total: fmt(cfg.total, cfg), left: fmt(s.left, cfg) });
                else if (required && !touched) msg = t('needOne');
            } else {
                var n = block.querySelectorAll('.budget-proj input:checked').length;
                var need = Math.max(cfg.min_items || 0, required ? 1 : 0);
                if (n < need) msg = t('needMin', { n: need });
            }
            block.querySelector('[data-budget-hint]').textContent = msg;
            if (msg && !first) first = block;
        });
        var g = firstInvalidGroup(form);
        if (g && !first) first = g;
        return first;
    }

    function initAll(root) {
        (root || document).querySelectorAll('[data-budget]').forEach(initBudget);
    }

    window.BudgetQuestion = {
        admit: admit,
        drawing: drawing,
        refreshGroups: refreshGroups,
        firstInvalid: firstInvalid,
        format: fmt,
        initAll: initAll,
        _layersFor: null,
    };

    document.addEventListener('DOMContentLoaded', function () { initAll(document); });
    document.addEventListener('htmx:afterSwap', function (e) { initAll(e.target); });
})();
