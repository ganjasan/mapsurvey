/* Translations tab (change translation-table).
 *
 * Rows autosave: a plain field posts on change, a rich field (Quill, created on
 * first click) posts when it loses focus. The server answers with the row's
 * `<tbody>` re-rendered (our own template, over text that already passed the
 * creator-HTML allow-list), which replaces the old one, and a counts header for
 * the status chips. The language pair, the split rows and the open usage lists
 * are remembered per survey in localStorage (`msTranslations:<uuid>`). */
(function () {
    'use strict';
    var page = document.getElementById('translations');
    if (!page) return;
    var SURVEY = page.dataset.survey;
    var SAVE_URL = page.dataset.saveUrl;
    var ADD_URL = page.dataset.addUrl;
    var CAN_EDIT = page.dataset.canEdit === '1';
    var STORE = 'msTranslations:' + SURVEY;

    function csrf() {
        return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
            (document.querySelector('input[name=csrfmiddlewaretoken]') || {}).value || '';
    }
    function load() { try { return JSON.parse(localStorage.getItem(STORE) || '{}'); } catch (e) { return {}; } }
    function store(patch) {
        try {
            var cur = load();
            Object.keys(patch).forEach(function (k) { cur[k] = patch[k]; });
            localStorage.setItem(STORE, JSON.stringify(cur));
        } catch (e) { /* private window: nothing to remember */ }
    }
    function parseRow(html) {
        // The server's own partial; DOMParser keeps scripts inert either way.
        var doc = new DOMParser().parseFromString('<table>' + html + '</table>', 'text/html');
        return doc.querySelector('tbody');
    }
    var memory = load();

    /* ── Language pair: URL first, else the remembered one ───────────── */
    var langs = document.getElementById('tt-langs');
    if (langs) {
        var url = new URL(location.href);
        if (!url.searchParams.get('to') && memory.to && page.dataset.to !== memory.to &&
            langs.querySelector('[name=to] option[value="' + memory.to + '"]')) {
            url.searchParams.set('from', memory.from || page.dataset.from);
            url.searchParams.set('to', memory.to);
            location.replace(url.toString());
            return;
        }
        store({ from: page.dataset.from, to: page.dataset.to });
        langs.addEventListener('change', function (evt) {
            var to = langs.querySelector('[name=to]');
            if (evt.target === to && to.value === '__add__') {
                to.value = page.dataset.to;
                var add = document.getElementById('tt-add');
                if (add) { add.hidden = false; var s = add.querySelector('#lang-search'); if (s) s.focus(); }
                return;
            }
            store({ from: langs.querySelector('[name=from]').value, to: to.value });
            langs.submit();
        });
    }

    /* ── Add a language: the settings picker, one addition at a time ──── */
    var hidden = document.getElementById('id_available_languages');
    if (hidden) {
        var before = [];
        try { before = JSON.parse(hidden.value || '[]'); } catch (e) {}
        hidden.addEventListener('change', function () {
            var now = [];
            try { now = JSON.parse(hidden.value || '[]'); } catch (e) {}
            var added = now.filter(function (c) { return before.indexOf(c) === -1; });
            if (!added.length) { hidden.value = JSON.stringify(before); return; }
            var fd = new FormData();
            fd.append('language', added[0]);
            fetch(ADD_URL, { method: 'POST', body: fd, headers: { 'X-CSRFToken': csrf() }, credentials: 'same-origin' })
                .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
                .then(function (res) {
                    if (res.ok && res.j.redirect) { store({ to: added[0] }); location.href = res.j.redirect; }
                    else { window.alert(res.j.error || 'Could not add the language.'); hidden.value = JSON.stringify(before); }
                })
                .catch(function () { hidden.value = JSON.stringify(before); });
        });
        var close = document.getElementById('tt-add-close');
        if (close) close.addEventListener('click', function () { document.getElementById('tt-add').hidden = true; });
    }

    /* ── Status chips: filter + live counts ───────────────────────────── */
    var state = document.getElementById('tt-state');
    function setState(s, text) {
        if (!state) return;
        state.dataset.state = s;
        state.textContent = text || '';
    }
    var filter = 'all';
    function applyFilter() {
        document.querySelectorAll('.tt-group').forEach(function (g) {
            g.style.display = (filter === 'all' || g.dataset.status === filter) ? '' : 'none';
        });
        document.querySelectorAll('.tt-page-row').forEach(function (p) {
            var any = false, el = p.nextElementSibling;
            while (el && !el.classList.contains('tt-page-row')) { if (el.style.display !== 'none') any = true; el = el.nextElementSibling; }
            p.style.display = any ? '' : 'none';
        });
    }
    document.querySelectorAll('.tt-chip').forEach(function (chip) {
        chip.addEventListener('click', function () {
            document.querySelectorAll('.tt-chip').forEach(function (c) { c.classList.remove('on'); });
            chip.classList.add('on');
            filter = chip.dataset.filter;
            applyFilter();
        });
    });
    function setCounts(counts) {
        if (!counts) return;
        Object.keys(counts).forEach(function (k) {
            var el = document.querySelector('[data-count="' + k + '"]');
            if (el) el.textContent = counts[k];
        });
    }

    /* ── Rows ─────────────────────────────────────────────────────────── */
    var splits = memory.splits || [];
    function splitList() { return splits.join(','); }

    function save(key, value, group) {
        var fd = new FormData();
        fd.append('key', key);
        fd.append('value', value);
        fd.append('from', page.dataset.from);
        fd.append('to', page.dataset.to);
        fd.append('split', splitList());
        setState('saving');
        var note = group.querySelector('.tt-saved');
        return fetch(SAVE_URL, { method: 'POST', body: fd, headers: { 'X-CSRFToken': csrf() }, credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) {
                    return r.json().catch(function () { return {}; }).then(function (j) { throw new Error(j.error || ('HTTP ' + r.status)); });
                }
                var counts = r.headers.get('X-TT-Counts');
                return r.text().then(function (html) {
                    var fresh = parseRow(html);
                    if (fresh) {
                        if (group.classList.contains('open')) fresh.classList.add('open');
                        group.replaceWith(fresh);
                        wire(fresh);
                    }
                    try { setCounts(JSON.parse(counts || 'null')); } catch (e) {}
                    setState('saved', page.dataset.liveNote || '');
                    applyFilter();
                });
            })
            .catch(function (err) {
                setState('error', err.message || 'Not saved');
                if (note) { note.textContent = err.message || 'Not saved'; note.classList.add('error'); }
            });
    }

    function initRich(box) {
        if (box.dataset.ready || !window.Quill) return null;
        var shell = box.querySelector('.tt-rich-shell');
        var html = shell ? shell.innerHTML : '';
        box.replaceChildren();
        var editor = document.createElement('div');
        box.appendChild(editor);
        var quill = new Quill(editor, {
            theme: 'snow',
            modules: { toolbar: [['bold', 'italic', 'underline'], [{ list: 'ordered' }, { list: 'bullet' }], ['link'], ['clean']] },
        });
        quill.setContents(quill.clipboard.convert({ html: html }), 'silent');
        box.dataset.ready = '1';
        var dirty = false;
        quill.on('text-change', function (d, o, src) { if (src === 'user') dirty = true; });
        quill.on('selection-change', function (range) {
            if (range === null && dirty) {
                dirty = false;
                var out = quill.root.innerHTML;
                if (out === '<p><br></p>') out = '';
                save(box.dataset.key, out, box.closest('.tt-group'));
            }
        });
        quill.focus();
        return quill;
    }

    function wire(group) {
        var uses = group.querySelector('.tt-uses');
        if (uses) uses.addEventListener('click', function () { group.classList.toggle('open'); });
        if (!CAN_EDIT) return;
        group.querySelectorAll('.tt-field').forEach(function (field) {
            field.addEventListener('change', function () { save(field.dataset.key, field.value, group); });
            // Grow with the text while typing; measuring at wire time would read
            // 0 for a field inside a hidden sub-row and leave it collapsed.
            field.addEventListener('input', function () { field.style.height = 'auto'; field.style.height = Math.max(field.scrollHeight, 34) + 'px'; });
        });
        group.querySelectorAll('.tt-rich').forEach(function (box) {
            if (box.dataset.readonly) return;
            box.addEventListener('click', function () { initRich(box); }, { once: true });
        });
        var splitBtn = group.querySelector('.tt-split-btn');
        if (splitBtn) splitBtn.addEventListener('click', function () {
            if (splits.indexOf(group.dataset.key) === -1) splits.push(group.dataset.key);
            store({ splits: splits });
            group.classList.add('split');
        });
        var merge = group.querySelector('.tt-merge');
        if (merge) merge.addEventListener('click', function () {
            splits = splits.filter(function (k) { return k !== group.dataset.key; });
            store({ splits: splits });
            var first = group.querySelector('.tt-sub .tt-field, .tt-sub .tt-rich-shell, .tt-sub .ql-editor');
            var value = first ? (first.value !== undefined ? first.value : first.innerHTML) : '';
            save(group.dataset.key, value, group);
        });
    }

    document.querySelectorAll('.tt-group').forEach(function (group) {
        if (splits.indexOf(group.dataset.key) !== -1) group.classList.add('split');
        wire(group);
    });

    /* ── Deep link: #row-<key>, where the key may be an occurrence key ─── */
    function jump() {
        var hash = decodeURIComponent(location.hash || '');
        if (hash.indexOf('#row-') !== 0) return;
        var key = hash.slice(5);
        var target = document.getElementById('row-' + key);
        var group = target ? target.closest('.tt-group') : null;
        if (!group) {
            document.querySelectorAll('.tt-group').forEach(function (g) {
                if ((' ' + g.dataset.occKeys + ' ').indexOf(' ' + key + ' ') !== -1) group = g;
            });
        }
        if (!group) return;
        filter = 'all'; applyFilter();
        group.classList.add('target');
        if (target && target.classList.contains('tt-sub')) group.classList.add('split');
        (target || group).scrollIntoView({ block: 'center' });
        var field = (target || group).querySelector('.tt-field');
        if (field && CAN_EDIT) field.focus();
    }
    jump();
    window.addEventListener('hashchange', jump);

    /* ── Import dialog ─────────────────────────────────────────────────── */
    var importBtn = document.getElementById('tt-import-btn');
    var importBox = document.getElementById('tt-import');
    if (importBtn && importBox) {
        importBtn.addEventListener('click', function () { importBox.hidden = false; });
        document.getElementById('tt-import-cancel').addEventListener('click', function () { importBox.hidden = true; });
        importBox.addEventListener('click', function (e) { if (e.target === importBox) importBox.hidden = true; });
    }
})();
