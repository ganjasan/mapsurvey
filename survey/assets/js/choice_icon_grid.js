/* Icon grid behaviour (spec choice-icon-grid; markup in templates/choice_icon_grid.html).
 *
 * The tiles are native radios/checkboxes, so selection, validation and keyboard need
 * nothing from here. This file does two things:
 *
 *  - keeps the `cig-tile--on` class in step with the inputs (the look on browsers
 *    without :has(), and after a pop-up restored values with .prop() and no events);
 *  - for single choice (`data-cig-collapse`), folds the grid to the visual row that
 *    holds the checked tile, with a "Show all options" button to unfold it.
 *
 * Rows are read from layout (offsetTop), never from a column count, so the fold follows
 * the pop-up's and the phone's width. A grid that cannot be measured (hidden, 0×0)
 * stays expanded: that is the fail-open state.
 *
 * Listeners are delegated on document, so pop-ups built after load work. Pop-ups call
 * window.syncIconGrids(popupElement) after restoring stored values (initPopupFields).
 */
(function () {
    'use strict';
    if (window.syncIconGrids) return;

    function grids(root) {
        root = root || document;
        var list = Array.prototype.slice.call(root.querySelectorAll('[data-choice-icon-grid]'));
        if (root.matches && root.matches('[data-choice-icon-grid]')) list.unshift(root);
        return list;
    }

    function paint(grid) {
        grid.querySelectorAll('.cig-tile').forEach(function (tile) {
            var input = tile.querySelector('.cig-tile__input');
            tile.classList.toggle('cig-tile--on', !!(input && input.checked));
        });
    }

    function expand(grid) {
        grid.classList.remove('cig-collapsed');
        grid.querySelectorAll('.cig-off-row').forEach(function (el) { el.classList.remove('cig-off-row'); });
        var btn = grid.querySelector('.cig-show-all');
        if (btn) btn.hidden = true;
    }

    function collapse(grid) {
        if (!grid.hasAttribute('data-cig-collapse')) return;
        expand(grid);   // measure the full layout
        var checked = grid.querySelector('.cig-tile__input:checked');
        if (!checked) return;
        var chosen = checked.closest('.cig-tile');
        if (!chosen || !chosen.offsetParent || chosen.offsetHeight === 0) return;
        var top = chosen.offsetTop;
        var tiles = grid.querySelectorAll('.cig-tile');
        if (tiles.length < 2) return;
        var hidden = 0;
        tiles.forEach(function (tile) {
            var off = Math.abs(tile.offsetTop - top) > 2;
            tile.classList.toggle('cig-off-row', off);
            if (off) hidden += 1;
        });
        if (!hidden) return;   // everything fits on one row — nothing to fold
        grid.querySelectorAll('.cig-run').forEach(function (run) {
            run.classList.toggle('cig-off-row', !run.querySelector('.cig-tile:not(.cig-off-row)'));
        });
        grid.classList.add('cig-collapsed');
        var btn = grid.querySelector('.cig-show-all');
        if (btn) btn.hidden = false;
    }

    function sync(root) {
        grids(root).forEach(function (grid) { paint(grid); collapse(grid); });
    }

    document.addEventListener('change', function (e) {
        var input = e.target;
        if (!input.classList || !input.classList.contains('cig-tile__input')) return;
        var grid = input.closest('[data-choice-icon-grid]');
        if (!grid) return;
        paint(grid);
        collapse(grid);
    });

    document.addEventListener('click', function (e) {
        var btn = e.target.closest && e.target.closest('.cig-show-all');
        if (!btn) return;
        var grid = btn.closest('[data-choice-icon-grid]');
        if (!grid) return;
        e.preventDefault();
        expand(grid);
        var checked = grid.querySelector('.cig-tile__input:checked');
        if (checked) checked.focus({ preventScroll: true });
    });

    var resizeTimer = null;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            grids(document).forEach(function (grid) {
                if (grid.classList.contains('cig-collapsed')) collapse(grid);
            });
        }, 150);
    });

    document.addEventListener('DOMContentLoaded', function () { sync(document); });
    document.addEventListener('htmx:afterSwap', function (e) { sync(e.target); });

    window.syncIconGrids = sync;
})();
