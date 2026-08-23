/* Mobile pane switching (openspec: mobile-adaptive-refactor).
 *
 * The three desktop panes stay in the DOM; below 768px exactly one is shown,
 * driven by `data-active-pane` on .editor-container (see editor-mobile.css).
 * Switching is pure client state — no reload, so pane state (selected
 * question, scroll position, preview iframe) survives round-trips between
 * panes. Loaded only when MOBILE_EDITOR_NAV is on.
 */
(function () {
    'use strict';

    function container() {
        // Survey tab uses .editor-container; Public results uses .pr-container.
        return document.querySelector('.editor-container, .pr-container');
    }

    function setPane(name) {
        var c = container();
        if (!c) return;
        c.setAttribute('data-active-pane', name);
        document.querySelectorAll('.mobile-tabbar button[data-pane]').forEach(function (btn) {
            btn.classList.toggle('active', btn.getAttribute('data-pane') === name);
        });
        // Preview owns the whole screen on mobile (owner review): tab bar and
        // context bars hide, exit is the ‹ button injected into its header.
        document.body.classList.toggle('pane-preview-full', name === 'preview');
        if (name === 'preview') injectPreviewBack();
    }

    function injectPreviewBack() {
        var head = document.querySelector('.editor-preview .preview-header, .pr-preview .pr-preview-head');
        if (!head || head.querySelector('.mobile-preview-back')) return;
        var back = document.createElement('button');
        back.type = 'button';
        back.className = 'mobile-preview-back';
        back.setAttribute('aria-label', 'Close preview');
        var icon = document.createElement('i');
        icon.className = 'fas fa-chevron-left';
        back.appendChild(icon);
        back.addEventListener('click', function () { setPane('structure'); });
        head.insertBefore(back, head.firstChild);
    }

    // Drill-down (Structure → question tap) and the type picker need to switch
    // panes programmatically.
    window.mobileNavSetPane = setPane;

    function isMobile() {
        return window.matchMedia('(max-width: 767.98px)').matches;
    }

    document.addEventListener('DOMContentLoaded', function () {
        var bar = document.querySelector('.mobile-tabbar');
        if (!bar) return;
        bar.addEventListener('click', function (e) {
            var btn = e.target.closest('button[data-pane]');
            if (btn) setPane(btn.getAttribute('data-pane'));
        });
        var initial = bar.querySelector('button.active') || bar.querySelector('button[data-pane]');
        if (initial) setPane(initial.getAttribute('data-pane'));

        // Drill-down: picking a section (or a pinned item like Survey settings)
        // in Structure jumps to the Edit pane, where that section's content
        // loads. Desktop behavior is untouched — the guard keeps this a mobile
        // -only navigation, and the existing click handlers still run.
        var sidebar = document.querySelector('.editor-sidebar');
        if (sidebar) {
            sidebar.addEventListener('click', function (e) {
                if (!isMobile()) return;
                if (e.target.closest('.section-delete, .section-action, .drag-handle')) return;
                if (e.target.closest('.section-item, .sidebar-pinned-item')) setPane('edit');
            });
        }

        // Breadcrumb back from Edit to Structure (shown <768px via CSS).
        var main = document.querySelector('.editor-main, .pr-main');
        if (main && !main.querySelector('.mobile-pane-back')) {
            var back = document.createElement('button');
            back.type = 'button';
            back.className = 'mobile-pane-back';
            var icon = document.createElement('i');
            icon.className = 'fas fa-chevron-left';
            back.appendChild(icon);
            var label = main.classList.contains('pr-main') ? ' Blocks' : ' Sections';
            back.appendChild(document.createTextNode(label));
            back.addEventListener('click', function () { setPane('structure'); });
            main.insertBefore(back, main.firstChild);
        }
    });
}());
