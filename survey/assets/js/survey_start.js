/* Ways to start (openspec: first-survey-onboarding, start-cards-one-click).
 *
 * One job: the "Start from scratch" form asks the browser where the creator
 * is, tied to the click that submits it, and never on page load. Permission
 * already granted -> read silently; not asked yet -> ask now, the sentence
 * on the card having said why; denied -> straight to the server, whose chain
 * (workspace's last survey, country, world) decides. Three seconds is the
 * ceiling either way: a survey is created with or without the point.
 *
 * Used by the start page, where the whole card is the submit button, and by
 * the dashboard's "+ New Survey" once the creator made "from scratch" their
 * default.
 */
window.SurveyStart = (function () {
    'use strict';

    var CEILING_MS = 3000;

    function fill(form, pos) {
        var lat = form.querySelector('[name="map_lat"]');
        var lng = form.querySelector('[name="map_lng"]');
        var zoom = form.querySelector('[name="map_zoom"]');
        if (lat) lat.value = pos.coords.latitude;
        if (lng) lng.value = pos.coords.longitude;
        if (zoom && !zoom.value) zoom.value = 13;
    }

    function bindBlankForm(form) {
        if (!form || form.dataset.geoBound) return;
        form.dataset.geoBound = '1';
        form.addEventListener('submit', function (e) {
            if (form.dataset.geoDone || !navigator.geolocation) return;
            e.preventDefault();
            var button = form.querySelector('[type="submit"]');
            if (button) {
                button.disabled = true;
                // The start page's card is the button itself: write the label
                // into its slot instead of wiping the card's picture and text.
                var slot = button.querySelector('[data-busy-target]') || button;
                if (button.dataset.busyLabel) slot.textContent = button.dataset.busyLabel;
            }
            var done = false;
            function finish() {
                if (done) return;
                done = true;
                form.dataset.geoDone = '1';
                // form.submit() fires no submit event, so hold the loading bar by hand.
                if (window.LoadingFeedback) window.LoadingFeedback.start();
                form.submit();
            }
            var timer = setTimeout(finish, CEILING_MS);
            function ask() {
                navigator.geolocation.getCurrentPosition(function (pos) {
                    fill(form, pos);
                    clearTimeout(timer);
                    finish();
                }, function () {
                    clearTimeout(timer);
                    finish();
                }, { enableHighAccuracy: false, timeout: CEILING_MS, maximumAge: 300000 });
            }
            if (navigator.permissions && navigator.permissions.query) {
                navigator.permissions.query({ name: 'geolocation' }).then(function (status) {
                    if (status.state === 'denied') { clearTimeout(timer); finish(); } else { ask(); }
                }, ask);
            } else {
                ask();
            }
        });
    }

    function bindAll(root) {
        var forms = (root || document).querySelectorAll('form[data-survey-start="blank"]');
        for (var i = 0; i < forms.length; i++) bindBlankForm(forms[i]);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { bindAll(document); });
    } else {
        bindAll(document);
    }

    return { bindBlankForm: bindBlankForm, bindAll: bindAll };
})();
