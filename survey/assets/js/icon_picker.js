/* Marker icon picker for the question editor.
 *
 * IconPicker.attach(input, {catalogUrl, lang, strings})
 *
 * Replaces the icon_class <input> with ONE button showing the current icon (a dashed
 * "+" when there is none) — change icon-picker-one-button: the preview + text field +
 * grid button took three controls per choices-table row. The input stays in the DOM,
 * hidden, and is what the form submits. The button opens a panel placed with
 * position:fixed next to it, so no table cell or modal decides its size: a search box
 * with "Remove icon", category chips, a "No icon" tile and the grid. A query that is
 * itself a valid value (`fas fa-x`, `maki:x`) offers "Use <value>", which keeps pasted
 * Pro classes working without a text field. The catalog
 * (survey/assets/data/icon_catalog.json, built by scripts/build_icon_catalog.py) is
 * fetched the first time any picker on the page opens, and once only.
 *
 * Search: every whitespace token of the query must be a substring of the icon's
 * haystack — its terms in the UI language, its English terms, label and name — so
 * "bus stop" narrows and "остановк" finds the bus stop under a Russian UI.
 * Category and query combine. With nothing typed and "All" selected the grid opens on
 * the current value, then the Map set (Maki/Temaki — what most creators come for),
 * then Font Awesome in category order. At most MAX_CELLS cells render.
 *
 * Telemetry (guarded, no-op without PostHog): `icon_search_miss` once per distinct
 * zero-result query per open, after MISS_DELAY ms of silence; `icon_picked` with
 * how the value was reached (search / browse / typed).
 */
(function (global) {
    'use strict';

    var MAX_CELLS = 240;
    var MISS_DELAY = 700;

    var catalogPromise = null;
    function loadCatalog(url) {
        if (!catalogPromise) {
            catalogPromise = fetch(url, { credentials: 'same-origin' })
                .then(function (r) { if (!r.ok) throw new Error('catalog ' + r.status); return r.json(); })
                .then(indexCatalog)
                .catch(function (err) { catalogPromise = null; throw err; });
        }
        return catalogPromise;
    }

    function indexCatalog(cat) {
        cat.icons.forEach(function (icon) {
            var name = icon.v.replace(/^(fas|far|fab|fa) fa-/, '').replace(/^(maki|temaki):/, '');
            icon.set = icon.v.indexOf(':') !== -1 ? icon.v.split(':')[0] : 'fa';
            icon.name = name;
            icon.hay = {};
            var base = ' ' + name.replace(/[-_]/g, ' ') + ' ' + icon.l.toLowerCase() + ' ' + (icon.t.en || '') + ' ';
            Object.keys(icon.t).forEach(function (lang) {
                icon.hay[lang] = lang === 'en' ? base : base + icon.t[lang] + ' ';
            });
            icon.hay.en = base;
        });
        cat.byValue = {};
        cat.icons.forEach(function (icon) { cat.byValue[icon.v] = icon; });
        return cat;
    }

    function capture(event, props) {
        if (global.posthog && global.posthog.capture) {
            try { global.posthog.capture(event, props); } catch (e) { /* analytics never breaks the editor */ }
        }
    }

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text != null) node.textContent = text;
        return node;
    }

    function clear(node) {
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    function attach(input, opts) {
        if (!input || input.dataset.iconPickerAttached) return;
        input.dataset.iconPickerAttached = '1';
        opts = opts || {};
        var lang = (opts.lang || 'en').split('-')[0].toLowerCase();
        var S = Object.assign({
            search: 'Search icons…', all: 'All', narrow: 'Type to narrow the list',
            loading: 'Loading icons…', none: 'No icons match', failed: 'Could not load the icon catalog',
            browse: 'Browse icons', remove: 'Remove icon', noIcon: 'No icon', use: 'Use'
        }, opts.strings || {});

        var wrapper = el('div', 'icon-picker-wrapper');
        input.parentNode.insertBefore(wrapper, input);
        // The button IS the picker; the input only carries the value.
        var btn = el('button', 'icon-picker-trigger');
        btn.type = 'button';
        btn.setAttribute('aria-haspopup', 'dialog');
        wrapper.appendChild(btn);
        wrapper.appendChild(input);
        input.hidden = true;

        // Inside the wrapper (inside the Bootstrap modal, whose focus trap would pull
        // focus back out of a panel appended to <body>), placed with position:fixed.
        var dropdown = el('div', 'icon-picker-dropdown');
        dropdown.setAttribute('role', 'dialog');
        dropdown.setAttribute('aria-label', S.browse);
        var searchBox = el('div', 'icon-picker-search');
        var searchInput = el('input');
        searchInput.type = 'search';
        searchInput.placeholder = S.search;
        searchInput.setAttribute('aria-label', S.search);
        var removeBtn = el('button', 'icon-picker-remove', S.remove);
        removeBtn.type = 'button';
        searchBox.appendChild(searchInput);
        searchBox.appendChild(removeBtn);
        var chips = el('div', 'icon-picker-chips');
        var useRow = el('button', 'icon-picker-use');
        useRow.type = 'button';
        useRow.hidden = true;
        var status = el('div', 'icon-picker-status');
        var grid = el('div', 'icon-picker-grid');
        dropdown.appendChild(searchBox); dropdown.appendChild(chips);
        dropdown.appendChild(useRow);
        dropdown.appendChild(status); dropdown.appendChild(grid);
        wrapper.appendChild(dropdown);

        var catalog = null;
        var category = 'all';
        var lastQuery = '';
        var missTimer = null;
        var reportedMisses = {};

        function updatePreview() {
            var val = input.value.trim();
            clear(btn);
            btn.classList.toggle('icon-picker-trigger--empty', !val);
            if (val) {
                btn.appendChild(global.MarkerIcon.element(val, null, ''));
                btn.title = val;
            } else {
                btn.appendChild(el('i', 'fas fa-plus'));
                btn.title = S.browse;
            }
            btn.setAttribute('aria-label', btn.title);
            removeBtn.hidden = !val;
        }

        function setValue(value, via) {
            input.value = value;
            updatePreview();
            close();
            btn.focus();
            // Programmatic value set fires no input event; autosave and the live
            // preview listen for one.
            input.dispatchEvent(new Event('input', { bubbles: true }));
            if (value) {
                var icon = catalog && catalog.byValue[value];
                capture('icon_picked', { value: value, set: icon ? icon.set : (global.MarkerIcon.isSvgValue(value) ? value.split(':')[0] : 'fa'), via: via });
            }
        }

        // A query that is itself a value (pasted `fas fa-x`, `maki:x`) can be used as is.
        var VALUE_RE = /^((fas|far|fab|fa) fa-[a-z0-9-]+|(maki|temaki):[a-z0-9][a-z0-9_-]*)$/;
        function renderUseRow(raw) {
            var v = raw.trim();
            var show = VALUE_RE.test(v) && v !== input.value.trim();
            useRow.hidden = !show;
            if (!show) return;
            clear(useRow);
            useRow.appendChild(global.MarkerIcon.element(v, null, ''));
            useRow.appendChild(el('span', null, S.use + ' ' + v));
            useRow.dataset.value = v;
        }

        function categoryLabel(c) {
            return c.label[lang] || c.label.en || c.id;
        }

        function renderChips() {
            clear(chips);
            var all = [{ id: 'all', label: { en: S.all } }].concat(catalog.categories);
            all.forEach(function (c) {
                var chip = el('button', 'icon-picker-chip' + (c.id === category ? ' active' : ''), categoryLabel(c));
                chip.type = 'button';
                chip.dataset.category = c.id;
                chip.addEventListener('click', function () {
                    category = c.id;
                    renderChips();
                    renderGrid();
                });
                chips.appendChild(chip);
            });
        }

        function matches(icon, tokens) {
            if (category !== 'all' && icon.c.indexOf(category) === -1) return false;
            if (!tokens.length) return true;
            var hay = icon.hay[lang] || icon.hay.en;
            var en = icon.hay.en;
            for (var i = 0; i < tokens.length; i++) {
                if (hay.indexOf(tokens[i]) === -1 && en.indexOf(tokens[i]) === -1) return false;
            }
            return true;
        }

        function orderedIcons() {
            // Current value first, then the map sets, then Font Awesome by category order —
            // the catalog is already emitted in that order, so only the current value moves.
            var current = catalog.byValue[input.value.trim()];
            if (!current) return catalog.icons;
            return [current].concat(catalog.icons.filter(function (i) { return i !== current; }));
        }

        function renderGrid() {
            var q = searchInput.value.trim().toLowerCase();
            var tokens = q ? q.split(/\s+/) : [];
            clear(grid);
            var shown = 0, total = 0;
            var selected = input.value.trim();
            var icons = orderedIcons();
            if (!q) {
                // "No icon" first while browsing: the other way to clear besides Remove.
                var none = el('button', 'icon-picker-cell icon-picker-cell--none' + (selected ? '' : ' selected'));
                none.type = 'button';
                none.title = S.noIcon;
                none.setAttribute('aria-label', S.noIcon);
                none.dataset.value = '';
                none.appendChild(el('i', 'fas fa-ban'));
                none.addEventListener('click', onPick);
                grid.appendChild(none);
            }
            for (var i = 0; i < icons.length; i++) {
                var icon = icons[i];
                if (!matches(icon, tokens)) continue;
                total++;
                if (shown >= MAX_CELLS) continue;
                shown++;
                var cell = el('button', 'icon-picker-cell' + (icon.v === selected ? ' selected' : ''));
                cell.type = 'button';
                cell.title = icon.l + (icon.set === 'fa' ? '' : ' · ' + icon.set);
                cell.dataset.value = icon.v;
                cell.appendChild(global.MarkerIcon.element(icon.v, null, ''));
                cell.addEventListener('click', onPick);
                grid.appendChild(cell);
            }
            if (total === 0) {
                status.textContent = S.none;
                status.hidden = false;
                scheduleMiss(q);
            } else if (total > MAX_CELLS) {
                status.textContent = S.narrow + ' (' + total + ')';
                status.hidden = false;
                clearTimeout(missTimer);
            } else {
                status.hidden = true;
                clearTimeout(missTimer);
            }
            // The panel is short while the catalog loads; place it again at full height.
            place();
        }

        function scheduleMiss(q) {
            clearTimeout(missTimer);
            if (!q || reportedMisses[q]) return;
            missTimer = setTimeout(function () {
                if (searchInput.value.trim().toLowerCase() !== q || reportedMisses[q]) return;
                reportedMisses[q] = true;
                capture('icon_search_miss', { query: q, lang: lang, category: category });
            }, MISS_DELAY);
        }

        function onPick(e) {
            setValue(e.currentTarget.dataset.value, searchInput.value.trim() ? 'search' : 'browse');
        }

        // Fixed placement next to the button: below it when there is room, else above;
        // clamped into the viewport. Below 768px the CSS bottom sheet takes over and
        // the inline position is cleared.
        var MARGIN = 8;
        function place() {
            if (!dropdown.classList.contains('open')) return;
            if (window.innerWidth <= 768) {
                dropdown.style.left = dropdown.style.top = dropdown.style.maxHeight = '';
                return;
            }
            var t = btn.getBoundingClientRect();
            dropdown.style.maxHeight = '';
            var w = dropdown.offsetWidth, h = dropdown.offsetHeight;
            var left = Math.min(Math.max(MARGIN, t.left), window.innerWidth - w - MARGIN);
            var below = window.innerHeight - t.bottom - 4 - MARGIN;
            var above = t.top - 4 - MARGIN;
            var top;
            if (h <= below) {
                top = t.bottom + 4;
            } else if (h <= above) {
                top = t.top - h - 4;
            } else if (below >= above) {
                // Fits on neither side: take the roomier one and scroll the grid,
                // never cover the button that opened it.
                dropdown.style.maxHeight = below + 'px';
                top = t.bottom + 4;
            } else {
                dropdown.style.maxHeight = above + 'px';
                top = t.top - 4 - above;
            }
            dropdown.style.left = Math.round(left) + 'px';
            dropdown.style.top = Math.round(top) + 'px';
        }

        function open() {
            dropdown.classList.add('open');
            place();
            renderUseRow('');
            btn.setAttribute('aria-expanded', 'true');
            searchInput.value = '';
            lastQuery = '';
            reportedMisses = {};
            if (catalog) {
                renderChips();
                renderGrid();
                searchInput.focus();
                return;
            }
            status.textContent = S.loading;
            status.hidden = false;
            loadCatalog(opts.catalogUrl).then(function (cat) {
                catalog = cat;
                if (!dropdown.classList.contains('open')) return;
                renderChips();
                renderGrid();
                searchInput.focus();
            }).catch(function () {
                status.textContent = S.failed;
                status.hidden = false;
            });
        }

        function close() {
            if (!dropdown.classList.contains('open')) return;
            dropdown.classList.remove('open');
            btn.setAttribute('aria-expanded', 'false');
            clearTimeout(missTimer);
        }

        btn.setAttribute('aria-expanded', 'false');
        btn.addEventListener('click', function () {
            if (dropdown.classList.contains('open')) close(); else open();
        });
        searchInput.addEventListener('input', function () {
            var q = this.value.trim().toLowerCase();
            if (q === lastQuery) return;
            lastQuery = q;
            renderUseRow(this.value);
            if (catalog) renderGrid();
        });
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { e.stopPropagation(); close(); btn.focus(); }
            if (e.key === 'Enter') {
                // Enter must not submit the question form.
                e.preventDefault();
                if (!useRow.hidden) setValue(useRow.dataset.value, 'typed');
            }
        });
        useRow.addEventListener('click', function () { setValue(useRow.dataset.value, 'typed'); });
        removeBtn.addEventListener('click', function () { setValue('', 'removed'); });
        // Code that sets the hidden input (row rebuilds, star defaults) still repaints the button.
        input.addEventListener('input', updatePreview);
        window.addEventListener('resize', place);
        // Capture: the modal body scrolls, not the window.
        window.addEventListener('scroll', place, true);
        document.addEventListener('click', function (e) {
            // A chip or cell click re-renders its row, so by the time this runs the
            // target may already be detached — that is an inside click, not an outside one.
            if (e.target.isConnected && !wrapper.contains(e.target)) close();
        });

        updatePreview();
        return { open: open, close: close, refresh: updatePreview, set: function (v) { setValue(v || '', 'api'); } };
    }

    global.IconPicker = { attach: attach, _loadCatalog: loadCatalog, MAX_CELLS: MAX_CELLS };
})(window);
