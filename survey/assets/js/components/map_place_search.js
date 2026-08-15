/*
 * Place search for any Mapsurvey map — respondent-facing and creator-facing.
 *
 * Mapbox Search Box answers, and an OpenStreetMap geocoder fills the gap where
 * Mapbox knows no points of interest (most of the world outside North America
 * and Western Europe). Each provider has an adapter producing one shared result
 * shape, so nothing below them knows which one replied.
 *
 * Selecting a result moves the map view and does nothing else: no marker, no
 * answer, no form field. Dropping a point stays a deliberate act by the
 * respondent.
 *
 *   MapPlaceSearch.attach(map, { accessToken: '...' })            // Leaflet control
 *   MapPlaceSearch.attach(map, { accessToken: '...', container }) // render into existing DOM
 *
 * Returns null when no access token is configured — better an absent control
 * than one that 401s on every keystroke.
 */
(function (window, document) {
    'use strict';

    // Search Box rather than Geocoding v6: the geocoding index has no points of
    // interest, and a respondent naming a park or a station is the common case.
    // Billed per request, like the endpoint it replaced, so the throttles below
    // still bound the cost — see design.md for why not /suggest + /retrieve.
    var ENDPOINT = 'https://api.mapbox.com/search/searchbox/v1/forward';

    // OSM fallback. Mapbox's POI coverage is concentrated in North America and
    // Western Europe: measured, it finds nothing in Bishkek, little in Belo
    // Horizonte and Tokyo, while OSM knows all of it — those cities are mapped
    // by the people who live in them. Consulted only when Mapbox did not answer
    // the query (see primaryAnsweredQuery), and always fail-open. No key needed.
    var OSM_ENDPOINT = 'https://photon.komoot.io/api/';
    var OSM_TIMEOUT_MS = 1500;
    var OSM_MAX_RESULTS = 3;
    // Photon 400s on anything outside this set, so an unsupported language must
    // be omitted rather than passed through. Its default is local names, which
    // is what someone searching in Bishkek wants anyway.
    var OSM_LANGS = ['de', 'en', 'fr'];
    // Cities and admin areas are exactly what Mapbox already answered with;
    // taking them from OSM too would just duplicate the list.
    var OSM_SKIP_KEYS = ['place', 'boundary'];

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
        // `auto_complete` is what makes "<place name> <city>" work: without it
        // "Sportschwimmhalle Jena" returns three settlements called Jena and no
        // pool; with it the pool is the first result. Measured, not assumed.
        // Results are never retained, so no permanent-storage flag is needed.
        params.push('auto_complete=true');
        return ENDPOINT + '?' + params.join('&');
    }

    function cacheKey(query, map) {
        var centre = map.getCenter();
        // Rounded, so nudging the map does not invalidate the whole cache.
        return query.toLowerCase() + '|' + centre.lng.toFixed(2) + ',' + centre.lat.toFixed(2);
    }

    // ── Result shape ────────────────────────────────────────────────────────
    // Everything below the adapters works on this object alone, so the UI never
    // learns which provider answered:
    //   {name, place, category, lat, lng, bounds, zoom, source}
    // `bounds` is Leaflet's [[south, west], [north, east]] or null.

    function fromMapbox(feature) {
        var props = feature.properties || {};
        var coords = (feature.geometry && feature.geometry.coordinates) || [];
        if (coords.length < 2) return null;
        var bbox = props.bbox;
        var categories = props.poi_category || [];
        return {
            name: props.name || props.full_address || '',
            place: props.place_formatted || '',
            // Two places can share a name — "Jena Paradies" is both a railway
            // station and a park — so the category is what tells them apart.
            // Up to two, because the array is not ordered specific-first: a park
            // comes back as ["outdoors", "park"], a station as ["train station",
            // "transport"]. Taking one would show a park as "outdoors".
            category: categories.slice(0, 2)
                .map(function (c) { return String(c).replace(/_/g, ' '); })
                .join(' · '),
            lat: coords[1],
            lng: coords[0],
            // Mapbox bbox is GeoJSON order: [west, south, east, north].
            bounds: (bbox && bbox.length === 4)
                ? [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
                : null,
            zoom: ZOOM_BY_TYPE[props.feature_type] || DEFAULT_ZOOM,
            source: 'mapbox'
        };
    }

    function fromPhoton(feature) {
        var props = feature.properties || {};
        var coords = (feature.geometry && feature.geometry.coordinates) || [];
        if (coords.length < 2 || !props.name) return null;

        var placeParts = [];
        if (props.housenumber && props.street) {
            placeParts.push(props.street + ' ' + props.housenumber);
        } else if (props.street) {
            placeParts.push(props.street);
        }
        if (props.postcode) placeParts.push(props.postcode);
        if (props.city) placeParts.push(props.city);
        if (props.country) placeParts.push(props.country);

        var extent = props.extent;
        return {
            name: props.name,
            place: placeParts.join(', '),
            category: String(props.osm_value || '').replace(/_/g, ' '),
            lat: coords[1],
            lng: coords[0],
            // NOT a GeoJSON bbox: Photon's extent is [west, north, east, south].
            // Measured — Bishkek arrives as [74.45, 43.01, 74.72, 42.72]. Passing
            // it through unconverted mirrors the viewport without any error.
            bounds: (extent && extent.length === 4)
                ? [[extent[3], extent[0]], [extent[1], extent[2]]]
                : null,
            zoom: ZOOM_BY_TYPE.poi,
            source: 'osm'
        };
    }

    function empty(node) {
        while (node.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    // ── OSM fallback ────────────────────────────────────────────────────────

    function osmUrl(query, map, options) {
        var centre = map.getCenter();
        var params = [
            'q=' + encodeURIComponent(query),
            'limit=' + RESULT_LIMIT,
            'lat=' + centre.lat.toFixed(4),
            'lon=' + centre.lng.toFixed(4)
        ];
        var lang = (options.language || '').slice(0, 2).toLowerCase();
        if (OSM_LANGS.indexOf(lang) > -1) {
            params.push('lang=' + lang);
        }
        return OSM_ENDPOINT + '?' + params.join('&');
    }

    function normalize(text) {
        return String(text || '').toLowerCase().replace(/[\s,.\-]+/g, ' ').trim();
    }

    // Did the primary provider actually answer the question that was asked?
    //
    // "Is there a POI in the response" is not the test — measured in Belo
    // Horizonte, "Mercado Central BH" comes back as five holiday rentals named
    // after the market ("Apto Dallas I Raul Soares Centro Mercado Central BH").
    // Those are POIs, and they are useless.
    //
    // A result answers the query when its name STARTS with the query's first
    // word: "Sportschwimmhalle Jena" → "Sportschwimmhalle Schwimmparadies" is
    // an answer; "Mercado Central BH" → "Apto Dallas ..." is not, even though it
    // contains every word of the query further along. Cheap, and it separates
    // the cases we measured.
    function primaryAnsweredQuery(query, results) {
        var lead = normalize(query).split(' ')[0];
        if (!lead) return true;
        return results.some(function (r) {
            return normalize(r.name).indexOf(lead) === 0;
        });
    }

    function samePlace(a, b) {
        // ~100m. Names are not compared: the two providers spell the same place
        // differently, and two rows that fly the map to one spot are the bug.
        return a.lat.toFixed(3) === b.lat.toFixed(3) && a.lng.toFixed(3) === b.lng.toFixed(3);
    }

    // Resolves to the results to prepend — never rejects. A dead or slow OSM
    // instance has to look exactly like "nothing extra was found".
    function fetchOsmPois(query, map, options, existing) {
        var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
        var timer = null;

        // The deadline is a race, not just an abort. Aborting assumes the
        // transport honours the signal; racing guarantees the list renders on
        // time whatever the network layer decides to do.
        var deadline = new Promise(function (resolve) {
            timer = setTimeout(function () {
                if (controller) controller.abort();   // stop the request too
                resolve([]);
            }, OSM_TIMEOUT_MS);
        });

        var lookup = fetch(osmUrl(query, map, options), controller ? { signal: controller.signal } : {})
            .then(function (response) {
                if (!response.ok) throw new Error('osm lookup failed: ' + response.status);
                return response.json();
            })
            .then(function (data) {
                var features = (data && data.features) || [];
                var picked = [];
                features.forEach(function (feature) {
                    if (picked.length >= OSM_MAX_RESULTS) return;
                    var props = feature.properties || {};
                    if (OSM_SKIP_KEYS.indexOf(props.osm_key) > -1) return;
                    var result = fromPhoton(feature);
                    if (!result) return;
                    var duplicate = existing.concat(picked).some(function (other) {
                        return samePlace(result, other);
                    });
                    if (!duplicate) picked.push(result);
                });
                return picked;
            })
            .catch(function () { return []; })
            .then(function (picked) {
                if (timer) clearTimeout(timer);
                return picked;
            });

        return Promise.race([lookup, deadline]);
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
            results.forEach(function (result, index) {
                var li = document.createElement('li');
                li.className = 'map-search-result';
                li.id = uid + '-opt-' + index;
                li.setAttribute('role', 'option');
                li.setAttribute('aria-selected', 'false');

                var primary = document.createElement('span');
                primary.className = 'map-search-name';
                primary.textContent = result.name;
                if (result.category) {
                    var category = document.createElement('span');
                    category.className = 'map-search-category';
                    category.textContent = result.category;
                    primary.appendChild(category);
                }
                li.appendChild(primary);

                if (result.place) {
                    var secondary = document.createElement('span');
                    secondary.className = 'map-search-context';
                    secondary.textContent = result.place;
                    li.appendChild(secondary);
                }

                li.addEventListener('click', function () { select(index); });
                li.addEventListener('mouseenter', function () { highlight(index); });
                list.appendChild(li);
            });

            // ODbL: attribution is owed wherever OSM data is shown, and only
            // there — a list of pure Mapbox results carries none.
            if (results.some(function (r) { return r.source === 'osm'; })) {
                var credit = document.createElement('li');
                credit.className = 'map-search-attribution';
                credit.setAttribute('role', 'presentation');
                var link = document.createElement('a');
                link.href = 'https://www.openstreetmap.org/copyright';
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = '© OpenStreetMap contributors';
                credit.appendChild(link);
                list.appendChild(credit);
            }

            list.hidden = false;
            input.setAttribute('aria-expanded', 'true');
            highlight(-1);
        }

        // Moves the map. Deliberately nothing else.
        function select(index) {
            var result = features[index];
            if (!result) return;

            if (result.bounds) {
                map.fitBounds(result.bounds);
            } else {
                map.flyTo([result.lat, result.lng], result.zoom, { animate: true, duration: 0.8 });
            }

            input.value = result.name;
            closeList();
            if (typeof options.onSelect === 'function') {
                options.onSelect(result);
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
                    var results = ((data && data.features) || [])
                        .map(fromMapbox)
                        .filter(Boolean);

                    // Consult OSM only when the primary provider did not answer
                    // the query — "Ошский рынок" comes back as a street, "ЦУМ
                    // Бишкек" as the city, "Mercado Central BH" as holiday
                    // rentals. When it did answer, no second request is made at
                    // all, which is the common case in Europe and the US.
                    if (primaryAnsweredQuery(query, results)) {
                        cache[key] = results;
                        render(results);
                        return;
                    }
                    return fetchOsmPois(query, map, options, results).then(function (osm) {
                        var merged = osm.concat(results);
                        cache[key] = merged;
                        render(merged);
                    });
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
