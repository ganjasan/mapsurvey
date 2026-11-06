/* The application sidebar (change app-sidebar, #538): Collapse/Expand, the phone drawer and
   the one navigation event. Markup: partials/_app_sidebar.html; styles: css/app_sidebar.css.

   Width: on a survey page (`app-rail-default` on <body>) the rail is the default and Expand
   lasts for the page; elsewhere the choice is remembered in localStorage['msSidebar'] and read
   before first paint by the inline script in the partial. */
(function () {
    'use strict';
    var body = document.body;
    var side = document.getElementById('appSidebar');
    if (!side) return;
    var toggle = document.getElementById('appSidebarToggle');
    var backdrop = document.getElementById('appSidebarBackdrop');
    var KEY = 'msSidebar';
    var phone = window.matchMedia('(max-width: 767.98px)');

    function syncToggleLabel() {
        if (!toggle) return;
        var rail = body.classList.contains('app-rail');
        var label = rail ? toggle.dataset.labelExpand : toggle.dataset.labelCollapse;
        toggle.setAttribute('aria-label', label);
        toggle.dataset.label = label;
        var span = toggle.querySelector('span');
        if (span) span.textContent = label;
    }

    if (toggle) {
        toggle.addEventListener('click', function () {
            var rail = !body.classList.contains('app-rail');
            body.classList.toggle('app-rail', rail);
            if (!body.classList.contains('app-rail-default')) {
                try { localStorage.setItem(KEY, rail ? 'rail' : 'wide'); } catch (e) {}
            }
            syncToggleLabel();
            // Leaflet maps and other measured panes re-read their width.
            window.dispatchEvent(new Event('resize'));
        });
    }
    syncToggleLabel();

    function openDrawer() {
        body.classList.add('app-drawer-open');
        if (backdrop) backdrop.hidden = false;
    }
    function closeDrawer() {
        body.classList.remove('app-drawer-open');
        if (backdrop) backdrop.hidden = true;
    }
    document.addEventListener('click', function (e) {
        if (e.target.closest('[data-app-drawer-open]')) { e.preventDefault(); openDrawer(); }
    });
    if (backdrop) backdrop.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && body.classList.contains('app-drawer-open')) closeDrawer();
    });

    side.addEventListener('click', function (e) {
        var link = e.target.closest('[data-nav-key]');
        if (!link) return;
        if (window.posthog && typeof window.posthog.capture === 'function') {
            window.posthog.capture('app_nav_clicked', {
                item: link.dataset.navKey,
                surface: phone.matches ? 'drawer' : 'sidebar'
            });
        }
        if (link.tagName === 'A') closeDrawer();
    });
})();
