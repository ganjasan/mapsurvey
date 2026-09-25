/*
 * ImageBasemap — a creator's uploaded picture as the map (change `custom-image-basemap`).
 *
 * The ONE renderer every map surface uses when a survey's basemap is an image.
 * It draws what the server hands it (survey/image_basemap.py::config_for):
 * {url, bounds: [[south, west], [north, east]], width, height}. The bounds are
 * never recomputed here — the picture sits on a fixed rectangle at 0°,0° in the
 * ordinary EPSG:3857 CRS, so draw tools, fitBounds and GeoJSON all work as on tiles.
 *
 *   var cfg = JSON.parse('{{ survey|image_basemap_json|escapejs }}');   // null on a tiles survey
 *   if (cfg) ImageBasemap.apply(map, cfg); else L.tileLayer(...)
 *
 * apply() confines the view to the picture (10 % margin), limits zoom to what
 * the picture's resolution supports and returns the picture's LatLngBounds;
 * the caller decides whether to fitBounds (it has no start view of its own) or
 * keep the one it was given.
 */
(function (global) {
    'use strict';

    // Zoom at which one picture pixel is one screen pixel: the picture's width
    // in pixels over the width its bounds occupy at zoom 0.
    function nativeZoom(map, cfg, bounds) {
        var crs = map.options.crs;
        var a = crs.latLngToPoint(bounds.getSouthWest(), 0);
        var b = crs.latLngToPoint(bounds.getNorthEast(), 0);
        var span = Math.abs(b.x - a.x);
        if (!span || !cfg.width) return map.getMaxZoom();
        return Math.log(cfg.width / span) / Math.LN2;
    }

    function apply(map, cfg, opts) {
        opts = opts || {};
        var bounds = L.latLngBounds(cfg.bounds);
        var overlay = L.imageOverlay(cfg.url, bounds, {
            interactive: false,
            className: 'image-basemap',
            pane: 'tilePane',
            attribution: opts.attribution || ''
        }).addTo(map);

        // Neutral surround instead of Leaflet's tile-loading grey.
        map.getContainer().style.background = '#f3f4f6';
        // A view off the picture (a real-world default, a stale position) is
        // framed NOW, without animation: setMaxBounds would otherwise pan it in
        // with an animation whose moveend lands after the caller has wired its
        // own handlers — the map position picker saved that as a creator move.
        var size = map.getSize();
        if (size && size.x && size.y && !bounds.pad(0.1).contains(map.getCenter())) {
            map.fitBounds(bounds, { animate: false });
        }
        // Per map, not a page global: several maps share a page (Responses).
        map._imageBasemapBounds = bounds;
        map.setMaxBounds(bounds.pad(0.1));
        map.options.maxBoundsViscosity = 1.0;
        var maxZoom = Math.ceil(nativeZoom(map, cfg, bounds)) + 1;
        map.setMaxZoom(maxZoom);

        // minZoom needs a sized container; a hidden one (form sections, modals)
        // gets it on the first resize instead.
        function fitMin() {
            var size = map.getSize();
            if (!size || !size.x || !size.y) return false;
            map.setMinZoom(Math.max(0, map.getBoundsZoom(bounds) - 1));
            return true;
        }
        if (!fitMin()) map.once('resize', fitMin);
        else map.on('resize', fitMin);

        return { overlay: overlay, bounds: bounds };
    }

    function contains(cfg, lat, lng) {
        if (!cfg || !isFinite(lat) || !isFinite(lng)) return false;
        return L.latLngBounds(cfg.bounds).contains([lat, lng]);
    }

    global.ImageBasemap = { apply: apply, contains: contains };
})(window);
