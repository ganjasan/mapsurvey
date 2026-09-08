/* Browser half of survey/marker_icons.py — the ONE place that turns a
 * Question.icon_class value into a glyph.
 *
 * Two value forms:
 *   "fas fa-bus"    Font Awesome class list  → <i class="fas fa-bus …">
 *   "maki:bus"      sprite symbol            → <svg><use href="<sprite>#maki-bus">
 *
 * Sprite URLs come from <body data-icon-sprites='{"maki": "...", "temaki": "..."}'>,
 * rendered server-side with {% static %} so the hashed filenames are right. Unknown
 * "set:name" values fall back to the default pin; a Font Awesome-shaped string passes
 * through untouched, exactly as before this file existed. No caller should build icon
 * markup or prepend the legacy "fa " prefix itself.
 */
(function (global) {
    'use strict';

    var DEFAULT_PIN = 'fas fa-map-marker-alt';
    var SVG_RE = /^(maki|temaki):([a-z0-9][a-z0-9_-]*)$/;
    var SVG_NS = 'http://www.w3.org/2000/svg';
    var XLINK_NS = 'http://www.w3.org/1999/xlink';

    var spritesCache = null;
    function sprites() {
        if (spritesCache) return spritesCache;
        var raw = global.document && document.body && document.body.getAttribute('data-icon-sprites');
        try { spritesCache = raw ? JSON.parse(raw) : {}; } catch (e) { spritesCache = {}; }
        return spritesCache;
    }

    function resolve(value) {
        value = (value || '').trim();
        var m = value.match(SVG_RE);
        if (m) {
            var url = sprites()[m[1]];
            if (url) return { kind: 'svg', set: m[1], symbol: m[1] + '-' + m[2], href: url + '#' + m[1] + '-' + m[2] };
            return { kind: 'font', classes: DEFAULT_PIN };
        }
        return { kind: 'font', classes: value || DEFAULT_PIN };
    }

    /* A fresh DOM node for the glyph. `color` paints it (color: / fill:), `cssClass`
     * is what the surface positions it by (feature-icon, crosshair-pin-icon, …). */
    function element(value, color, cssClass) {
        var r = resolve(value);
        var el;
        if (r.kind === 'svg') {
            el = document.createElementNS(SVG_NS, 'svg');
            el.setAttribute('class', 'marker-icon-svg-glyph' + (cssClass ? ' ' + cssClass : ''));
            el.setAttribute('aria-hidden', 'true');
            el.setAttribute('focusable', 'false');
            var use = document.createElementNS(SVG_NS, 'use');
            use.setAttribute('href', r.href);
            use.setAttributeNS(XLINK_NS, 'xlink:href', r.href);
            el.appendChild(use);
            if (color) el.style.fill = color;
        } else {
            el = document.createElement('i');
            el.className = r.classes + (cssClass ? ' ' + cssClass : '');
            el.setAttribute('aria-hidden', 'true');
            if (color) el.style.color = color;
        }
        return el;
    }

    function html(value, color, cssClass) {
        return element(value, color, cssClass).outerHTML;
    }

    global.MarkerIcon = {
        DEFAULT_PIN: DEFAULT_PIN,
        resolve: resolve,
        element: element,
        html: html,
        isSvgValue: function (v) { return SVG_RE.test((v || '').trim()); },
        _resetSpriteCache: function () { spritesCache = null; }
    };
})(window);
