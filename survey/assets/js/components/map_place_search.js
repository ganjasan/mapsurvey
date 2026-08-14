/*
 * Place search for any Mapsurvey map — respondent-facing and creator-facing.
 *
 * One geocoder for the whole platform (Mapbox Geocoding v6). Selecting a result
 * moves the map view and does nothing else: no marker, no answer, no form field.
 * Dropping a point stays a deliberate act by the respondent.
 *
 *   MapPlaceSearch.attach(map, { accessToken: '...' })            // Leaflet control
 *   MapPlaceSearch.attach(map, { accessToken: '...', container }) // render into existing DOM
 *
 * Returns null when no access token is configured — better an absent control
 * than one that 401s on every keystroke.
 */
(function (window, document) {
    'use strict';

    var ENDPOINT = 'https://api.mapbox.com/search/geocode/v6/forward';

    var MIN_CHARS = 3;
    var DEBOUNCE_MS = 300;
    var RESULT_LIMIT = 5;

    // Mapbox bills each keystroke as a request when autocompleting, so a query
    // is only ever sent once typing pauses — see design.md.

    // How close to fly when a result carries no bbox of its own.
    var ZOOM_BY_TYPE = {
        country: 4,
        region: 6,
        district: 8,
        place: 11,
        postcode: 12,
        locality: 12,
        neighborhood: 14,
        street: 16,
        address: 17,
        poi: 17
    };
    var DEFAULT_ZOOM = 13;

    var DEFAULT_LABELS = {
        placeholder: 'Search address...',
        ariaLabel: 'Search the map for a place',
        noResults: 'No results found',
        failed: 'Search failed — check your connection and try again.'
    };

    var idCounter = 0;

    function buildUrl(query, map, options) {
        var centre = map.getCenter();
        var params = [
            'q=' + encodeURIComponent(query),
            'access_token=' + encodeURIComponent(options.accessToken),
            'limit=' + RESULT_LIMIT,
            // Bias to what the creator framed: a street name that exists in a
            // hundred towns should resolve to the one this survey is about.
            'proximity=' + centre.lng.toFixed(4) + ',' + centre.lat.toFixed(4)
        ];
        if (options.language) {
            params.push('language=' + encodeURIComponent(options.language));
        }
        // `permanent` is left at its default of false — we never retain results.
        return ENDPOINT + '?' + params.join('&');
    }

    function cacheKey(query, map) {
        var centre = map.getCenter();
        // Rounded, so nudging the map does not invalidate the whole cache.
        return query.toLowerCase() + '|' + centre.lng.toFixed(2) + ',' + centre.lat.toFixed(2);
    }

    function describe(feature) {
        var props = feature.properties || {};
        return {
            primary: props.name || props.full_address || '',
            secondary: props.place_formatted || ''
        };
    }

    function empty(node) {
        while (node.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function create(map, options) {
        var labels = {};
        for (var key in DEFAULT_LABELS) {
            if (Object.prototype.hasOwnProperty.call(DEFAULT_LABELS, key)) {
                labels[key] = (options.labels && options.labels[key]) || DEFAULT_LABELS[key];
            }
        }

        var uid = 'mps-' + (++idCounter);
        var cache = {};
        var pending = null;      // AbortController of the in-flight request
        var debounceTimer = null;
        var features = [];
        var activeIndex = -1;

        var root = document.createElement('div');
        root.className = 'map-search' + (options.className ? ' ' + options.className : '');

        var icon = document.createElement('i');
        icon.className = 'fas fa-search';
        icon.setAttribute('aria-hidden', 'true');
        root.appendChild(icon);

        var input = document.createElement('input');
        input.type = 'text';
        input.id = uid + '-input';
        input.autocomplete = 'off';
        input.placeholder = labels.placeholder;
        input.setAttribute('aria-label', labels.ariaLabel);
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-controls', uid + '-list');
        root.appendChild(input);

        var list = document.createElement('ul');
        list.className = 'map-search-results';
        list.id = uid + '-list';
        list.setAttribute('role', 'listbox');
        list.hidden = true;
        root.appendChild(list);

        function closeList() {
            list.hidden = true;
            empty(list);
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
            features = [];
            activeIndex = -1;
        }

        function showMessage(text) {
            empty(list);
            var li = document.createElement('li');
            li.className = 'map-search-message';
            li.textContent = text;
            list.appendChild(li);
            list.hidden = false;
            input.setAttribute('aria-expanded', 'true');
            features = [];
            activeIndex = -1;
        }

        function highlight(index) {
            var items = list.querySelectorAll('.map-search-result');
            for (var i = 0; i < items.length; i++) {
                var selected = (i === index);
                items[i].classList.toggle('active', selected);
                items[i].setAttribute('aria-selected', selected ? 'true' : 'false');
            }
            activeIndex = index;
            if (index >= 0 && items[index]) {
                input.setAttribute('aria-activedescendant', items[index].id);
            } else {
                input.removeAttribute('aria-activedescendant');
            }
        }

        function render(results) {
            features = results;
            empty(list);
            if (!results.length) {
                showMessage(labels.noResults);
                return;
            }
            results.forEach(function (feature, index) {
                var text = describe(feature);
                var li = document.createElement('li');
                li.className = 'map-search-result';
                li.id = uid + '-opt-' + index;
                li.setAttribute('role', 'option');
                li.setAttribute('aria-selected', 'false');

                var primary = document.createElement('span');
                primary.className = 'map-search-name';
                primary.textContent = text.primary;
                li.appendChild(primary);

                if (text.secondary) {
                    var secondary = document.createElement('span');
                    secondary.className = 'map-search-context';
                    secondary.textContent = text.secondary;
                    li.appendChild(secondary);
                }

                li.addEventListener('click', function () { select(index); });
                li.addEventListener('mouseenter', function () { highlight(index); });
                list.appendChild(li);
            });
            list.hidden = false;
            input.setAttribute('aria-expanded', 'true');
            highlight(-1);
        }

        // Moves the map. Deliberately nothing else.
        function select(index) {
            var feature = features[index];
            if (!feature) return;

            var props = feature.properties || {};
            var bbox = props.bbox;
            if (bbox && bbox.length === 4) {
                map.fitBounds([[bbox[1], bbox[0]], [bbox[3], bbox[2]]]);
            } else {
                var coords = (feature.geometry && feature.geometry.coordinates) || [];
                if (coords.length < 2) return;
                var zoom = ZOOM_BY_TYPE[props.feature_type] || DEFAULT_ZOOM;
                map.flyTo([coords[1], coords[0]], zoom, { animate: true, duration: 0.8 });
            }

            input.value = describe(feature).primary;
            closeList();
            if (typeof options.onSelect === 'function') {
                options.onSelect(feature);
            }
        }

        function search(query) {
            var key = cacheKey(query, map);
            if (cache[key]) {
                render(cache[key]);
                return;
            }
            if (pending) pending.abort();
            var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
            pending = controller;

            fetch(buildUrl(query, map, options), controller ? { signal: controller.signal } : {})
                .then(function (response) {
                    if (!response.ok) throw new Error('geocoding failed: ' + response.status);
                    return response.json();
                })
                .then(function (data) {
                    pending = null;
                    var results = (data && data.features) || [];
                    cache[key] = results;
                    render(results);
                })
                .catch(function (error) {
                    if (error && error.name === 'AbortError') return;  // superseded, not a failure
                    pending = null;
                    showMessage(labels.failed);
                });
        }

        input.addEventListener('input', function () {
            var query = input.value.trim();
            clearTimeout(debounceTimer);
            if (query.length < MIN_CHARS) {
                if (pending) { pending.abort(); pending = null; }
                closeList();
                return;
            }
            debounceTimer = setTimeout(function () { search(query); }, DEBOUNCE_MS);
        });

        input.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                if (activeIndex >= 0) {
                    select(activeIndex);
                } else if (features.length) {
                    select(0);
                } else {
                    // Enter before the debounce fired — search now rather than
                    // leaving the respondent looking at an empty list.
                    var query = input.value.trim();
                    clearTimeout(debounceTimer);
                    if (query.length >= MIN_CHARS) search(query);
                }
                return;
            }
            if (event.key === 'ArrowDown' && features.length) {
                event.preventDefault();
                highlight((activeIndex + 1) % features.length);
            } else if (event.key === 'ArrowUp' && features.length) {
                event.preventDefault();
                highlight(activeIndex <= 0 ? features.length - 1 : activeIndex - 1);
            } else if (event.key === 'Escape') {
                closeList();
                input.blur();
            }
        });

        document.addEventListener('click', function (event) {
            if (!root.contains(event.target)) closeList();
        });

        return { root: root, input: input, close: closeList };
    }

    var MapPlaceSearch = {
        attach: function (map, options) {
            options = options || {};
            if (!options.accessToken) return null;   // no geocoder → no control

            var widget = create(map, options);

            if (options.container) {
                options.container.appendChild(widget.root);
                return widget;
            }

            var Control = L.Control.extend({
                options: { position: options.position || 'topleft' },
                onAdd: function () {
                    // The map must not pan or zoom under the cursor while the
                    // respondent is typing in or scrolling the result list.
                    L.DomEvent.disableClickPropagation(widget.root);
                    L.DomEvent.disableScrollPropagation(widget.root);
                    return widget.root;
                }
            });
            var control = new Control();
            map.addControl(control);
            widget.control = control;
            return widget;
        }
    };

    window.MapPlaceSearch = MapPlaceSearch;
})(window, document);
