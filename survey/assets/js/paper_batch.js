/* The batch page (change paper-photo-entry, #495): uploads and drag-to-move.
 *
 * Every file is its own request (XHR, so progress per file), three in flight,
 * one retry on a failed request. The drop zone stays live for the life of the
 * page: adding more files while earlier ones are being read is the normal case.
 * The sheet list polls itself through HTMX (see batch.html) and is swapped
 * whole, so the page wires SortableJS again after every swap. All text comes
 * from data-* attributes; nothing here writes markup from server data. */
(function () {
    'use strict';
    var root = document.getElementById('paper-batch');
    if (!root) return;
    var uploadUrl = root.dataset.uploadUrl;
    var listUrl = root.dataset.listUrl;
    var maxBytes = parseInt(root.dataset.maxBytes, 10) || 0;
    var csrf = root.dataset.csrf;
    var queue = document.getElementById('paper-queue');
    var drop = document.getElementById('paper-drop');
    var input = document.getElementById('paper-files');
    var pick = document.getElementById('paper-pick');
    var PARALLEL = 3;
    var pending = [];
    var active = 0;

    function row(file) {
        var li = document.createElement('li');
        var name = document.createElement('span');
        name.textContent = file.name;
        var bar = document.createElement('div');
        bar.className = 'progress';
        var fill = document.createElement('div');
        fill.className = 'progress-bar';
        fill.style.width = '0%';
        bar.appendChild(fill);
        var status = document.createElement('span');
        status.className = 'paper-queue__status';
        li.appendChild(name);
        li.appendChild(bar);
        li.appendChild(status);
        queue.appendChild(li);
        return { li: li, fill: fill, status: status };
    }

    function finish(ui, ok, message) {
        ui.fill.style.width = '100%';
        ui.fill.classList.toggle('bg-danger', !ok);
        ui.status.textContent = message || '';
        if (!ok) ui.status.classList.add('paper-queue__err');
        if (ok) setTimeout(function () { if (ui.li.parentNode) ui.li.parentNode.removeChild(ui.li); }, 4000);
        refreshList();
    }

    function send(item, attempt) {
        active += 1;
        var xhr = new XMLHttpRequest();
        xhr.open('POST', uploadUrl);
        xhr.setRequestHeader('X-CSRFToken', csrf);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.upload.addEventListener('progress', function (e) {
            if (e.lengthComputable) item.ui.fill.style.width = Math.round(e.loaded * 100 / e.total) + '%';
        });
        xhr.addEventListener('load', function () {
            active -= 1;
            if (xhr.status >= 200 && xhr.status < 300) {
                finish(item.ui, true, root.dataset.msgUploaded);
            } else if (xhr.status >= 500 && attempt < 1) {
                send(item, attempt + 1);
                return;
            } else {
                var msg = root.dataset.msgFailed;
                try { msg = JSON.parse(xhr.responseText).error || msg; } catch (e) { /* keep the default */ }
                finish(item.ui, false, msg);
            }
            next();
        });
        xhr.addEventListener('error', function () {
            active -= 1;
            if (attempt < 1) { send(item, attempt + 1); return; }
            finish(item.ui, false, root.dataset.msgFailed);
            next();
        });
        var form = new FormData();
        form.append('file', item.file, item.file.name);
        xhr.send(form);
    }

    function next() {
        while (active < PARALLEL && pending.length) send(pending.shift(), 0);
    }

    function add(files) {
        Array.prototype.forEach.call(files, function (file) {
            var ui = row(file);
            if (maxBytes && file.size > maxBytes) {
                finish(ui, false, root.dataset.msgTooLarge);
                return;
            }
            pending.push({ file: file, ui: ui });
        });
        next();
    }

    if (drop) {
        ['dragenter', 'dragover'].forEach(function (ev) {
            drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('is-over'); });
        });
        ['dragleave', 'drop'].forEach(function (ev) {
            drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('is-over'); });
        });
        drop.addEventListener('drop', function (e) { if (e.dataTransfer && e.dataTransfer.files) add(e.dataTransfer.files); });
        drop.addEventListener('click', function (e) { if (e.target === drop || e.target.closest('p, i')) input.click(); });
        drop.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
    }
    if (pick) pick.addEventListener('click', function (e) { e.stopPropagation(); input.click(); });
    if (input) input.addEventListener('change', function () { add(input.files); input.value = ''; });

    // The list: ask for a fresh copy now (an upload just landed) and keep polling.
    var list = document.getElementById('paper-list');
    function refreshList() {
        if (!list || !window.htmx) return;
        window.htmx.ajax('GET', listUrl, { target: '#paper-list', swap: 'innerHTML' });
    }

    // Drag a page between sheets (SortableJS, long-press on touch), posting the move.
    function wireSortable() {
        if (!window.Sortable || !list) return;
        Array.prototype.forEach.call(list.querySelectorAll('.paper-dropzone'), function (zone) {
            if (zone.dataset.sortable) return;
            zone.dataset.sortable = '1';
            new window.Sortable(zone, {
                group: 'paper-pages',
                draggable: '.paper-thumb',
                delay: 300,
                delayOnTouchOnly: true,
                onAdd: function (evt) {
                    var pageId = evt.item.dataset.page;
                    var sheet = evt.to.dataset.sheet;
                    var moveUrl = listUrl.replace(/list\/$/, 'pages/' + pageId + '/move/');
                    var body = new FormData();
                    body.append('sheet', sheet);
                    fetch(moveUrl, { method: 'POST', body: body, headers: { 'X-CSRFToken': csrf, 'HX-Request': 'true' }, credentials: 'same-origin' })
                        .then(function () { refreshList(); })
                        .catch(function () { refreshList(); });
                }
            });
        });
    }
    wireSortable();
    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.target && e.target.id === 'paper-list') wireSortable();
    });
})();
