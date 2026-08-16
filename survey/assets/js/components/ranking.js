/* Ranking question: drag or keyboard to reorder.
 *
 * The order lives in the DOM — each row carries a hidden input with its item
 * code, so moving a row moves its value and the form submits the ranking with
 * no serialisation step. Everything here only moves rows and repaints the
 * rank numbers.
 *
 * Initialised on load and after every htmx swap, because sections are swapped
 * in without a page load.
 */
(function () {
    'use strict';

    function repaint(list) {
        var rows = list.querySelectorAll('.ranking__item');
        rows.forEach(function (row, i) {
            var rank = row.querySelector('[data-ranking-rank]');
            if (rank) rank.textContent = i + 1;
            row.setAttribute('aria-posinset', i + 1);
            row.setAttribute('aria-setsize', rows.length);
        });
    }

    function announce(block, message) {
        var status = block.querySelector('[data-ranking-status]');
        if (status) status.textContent = message;
    }

    function move(list, row, delta) {
        var rows = Array.prototype.slice.call(list.querySelectorAll('.ranking__item'));
        var from = rows.indexOf(row);
        var to = from + delta;
        if (to < 0 || to >= rows.length) return false;
        if (delta < 0) {
            list.insertBefore(row, rows[to]);
        } else {
            list.insertBefore(row, rows[to].nextSibling);
        }
        repaint(list);
        return true;
    }

    function init(block) {
        if (block.dataset.rankingReady === '1') return;
        block.dataset.rankingReady = '1';

        var list = block.querySelector('[data-ranking-list]');
        if (!list) return;
        var dragged = null;
        var grabbed = null;

        list.addEventListener('dragstart', function (e) {
            var row = e.target.closest('.ranking__item');
            if (!row) return;
            dragged = row;
            row.classList.add('is-dragging');
            e.dataTransfer.effectAllowed = 'move';
            // Firefox refuses to start a drag without data set.
            e.dataTransfer.setData('text/plain', row.dataset.code || '');
        });

        list.addEventListener('dragend', function () {
            if (dragged) dragged.classList.remove('is-dragging');
            dragged = null;
            repaint(list);
        });

        list.addEventListener('dragover', function (e) {
            if (!dragged) return;
            e.preventDefault();
            var over = e.target.closest('.ranking__item');
            if (!over || over === dragged) return;
            var box = over.getBoundingClientRect();
            var below = e.clientY > box.top + box.height / 2;
            list.insertBefore(dragged, below ? over.nextSibling : over);
            repaint(list);
        });

        list.addEventListener('drop', function (e) { e.preventDefault(); });

        list.addEventListener('keydown', function (e) {
            var row = e.target.closest('.ranking__item');
            if (!row) return;

            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                if (grabbed === row) {
                    grabbed = null;
                    row.classList.remove('is-grabbed');
                    row.setAttribute('aria-grabbed', 'false');
                    announce(block, row.querySelector('.ranking__label').textContent.trim() +
                        ' dropped at position ' + (row.getAttribute('aria-posinset') || ''));
                } else {
                    if (grabbed) {
                        grabbed.classList.remove('is-grabbed');
                        grabbed.setAttribute('aria-grabbed', 'false');
                    }
                    grabbed = row;
                    row.classList.add('is-grabbed');
                    row.setAttribute('aria-grabbed', 'true');
                    announce(block, row.querySelector('.ranking__label').textContent.trim() +
                        ' picked up. Use the arrow keys to move it, Space to drop it.');
                }
                return;
            }

            if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
            e.preventDefault();
            var delta = e.key === 'ArrowUp' ? -1 : 1;

            if (grabbed === row) {
                if (move(list, row, delta)) {
                    row.focus();
                    announce(block, row.querySelector('.ranking__label').textContent.trim() +
                        ' moved to position ' + (row.getAttribute('aria-posinset') || ''));
                }
            } else {
                // Not carrying anything: arrows walk the list.
                var rows = Array.prototype.slice.call(list.querySelectorAll('.ranking__item'));
                var next = rows[rows.indexOf(row) + delta];
                if (next) next.focus();
            }
        });

        repaint(list);
    }

    function initAll(root) {
        (root || document).querySelectorAll('[data-ranking]').forEach(init);
    }

    // Listened for on document, not document.body: this file is loaded from
    // <head>, where body does not exist yet. htmx events bubble up to
    // document either way.
    document.addEventListener('DOMContentLoaded', function () { initAll(document); });
    document.addEventListener('htmx:afterSwap', function (e) { initAll(e.target); });
})();
