/* Uploads on Paper responses and on one paper response (change paper-photo-entry, #495).
 *
 * Every `[data-paper-upload]` zone uploads its files to `data-upload-url`, one
 * request per file and ONE at a time, so the server's order is the order the
 * operator chose; `data-sheet` drops them into that response. Progress per file,
 * one retry on a failed request. After each upload the zone asks HTMX for a
 * fresh copy of `data-refresh-url` into `data-refresh-target` (the list keeps
 * polling itself while pages are being read). The camera input opens the camera
 * itself on a phone: one shot per tap, straight into the queue. All text comes
 * from data-* attributes; nothing here writes markup from server data. */
(function () {
    'use strict';

    function wire(zone) {
        var input = zone.querySelector('.paper-files');
        var camera = zone.querySelector('.paper-camera');
        var pick = zone.querySelector('.paper-pick');
        var shoot = zone.querySelector('.paper-shoot');
        var queue = zone.nextElementSibling && zone.nextElementSibling.classList.contains('paper-queue')
            ? zone.nextElementSibling : null;
        var maxBytes = parseInt(zone.dataset.maxBytes, 10) || 0;
        var pending = [];
        var busy = false;
        var shots = 0;

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
            li.appendChild(name);
            li.appendChild(bar);
            li.appendChild(status);
            if (queue) queue.appendChild(li);
            return { li: li, fill: fill, status: status };
        }

        function refresh() {
            if (!window.htmx || !zone.dataset.refreshUrl) return;
            window.htmx.ajax('GET', zone.dataset.refreshUrl, { target: zone.dataset.refreshTarget, swap: 'innerHTML' });
        }

        function finish(ui, ok, message) {
            ui.fill.style.width = '100%';
            ui.fill.classList.toggle('bg-danger', !ok);
            ui.status.textContent = message || '';
            if (!ok) ui.status.classList.add('paper-queue__err');
            if (ok) setTimeout(function () { if (ui.li.parentNode) ui.li.parentNode.removeChild(ui.li); }, 4000);
            refresh();
        }

        function send(item, attempt) {
            busy = true;
            var xhr = new XMLHttpRequest();
            xhr.open('POST', zone.dataset.uploadUrl);
            xhr.setRequestHeader('X-CSRFToken', zone.dataset.csrf);
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.upload.addEventListener('progress', function (e) {
                if (e.lengthComputable) item.ui.fill.style.width = Math.round(e.loaded * 100 / e.total) + '%';
            });
            xhr.addEventListener('load', function () {
                if (xhr.status >= 200 && xhr.status < 300) {
                    finish(item.ui, true, zone.dataset.msgUploaded);
                } else if (xhr.status >= 500 && attempt < 1) {
                    send(item, attempt + 1);
                    return;
                } else {
                    var msg = zone.dataset.msgFailed;
                    try { msg = JSON.parse(xhr.responseText).error || msg; } catch (e) { /* keep the default */ }
                    finish(item.ui, false, msg);
                }
                busy = false;
                next();
            });
            xhr.addEventListener('error', function () {
                if (attempt < 1) { send(item, attempt + 1); return; }
                finish(item.ui, false, zone.dataset.msgFailed);
                busy = false;
                next();
            });
            var form = new FormData();
            form.append('file', item.file, item.file.name);
            if (zone.dataset.sheet) form.append('sheet', zone.dataset.sheet);
            xhr.send(form);
        }

        function next() {
            if (!busy && pending.length) send(pending.shift(), 0);
        }

        function add(files) {
            Array.prototype.forEach.call(files, function (file) {
                var ui = row(file);
                if (maxBytes && file.size > maxBytes) { finish(ui, false, zone.dataset.msgTooLarge); return; }
                pending.push({ file: file, ui: ui });
            });
            next();
        }

        ['dragenter', 'dragover'].forEach(function (ev) {
            zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add('is-over'); });
        });
        ['dragleave', 'drop'].forEach(function (ev) {
            zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove('is-over'); });
        });
        zone.addEventListener('drop', function (e) { if (e.dataTransfer && e.dataTransfer.files) add(e.dataTransfer.files); });
        if (pick && input) pick.addEventListener('click', function (e) { e.stopPropagation(); input.click(); });
        if (input) input.addEventListener('change', function () { add(input.files); input.value = ''; });
        if (shoot && camera) {
            shoot.addEventListener('click', function (e) { e.stopPropagation(); camera.click(); });
            camera.addEventListener('change', function () {
                var file = camera.files && camera.files[0];
                if (file) {
                    // A camera shot has a generic name (image.jpg on iOS): number it for the list.
                    shots += 1;
                    var ext = (file.name.split('.').pop() || 'jpg').toLowerCase();
                    try { file = new File([file], 'photo-' + String(shots).padStart(3, '0') + '.' + ext, { type: file.type }); } catch (err) { /* keep the original */ }
                    add([file]);
                }
                camera.value = '';
            });
        }
    }

    Array.prototype.forEach.call(document.querySelectorAll('[data-paper-upload]'), wire);
})();
