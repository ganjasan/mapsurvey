/* The browser renderer of public result payloads (change landing-results, #578).
 * Moved verbatim from the inline script of public_results.html so that /r/<slug>/ and site
 * pages draw charts, maps and object tables with ONE code path. `blocks` are the payloads of
 * survey/public_results.py::ReportService; `BASEMAPS` is a basemap table
 * (survey/basemaps.py::table_for) whose Mapbox entries already carry the access token.
 * Element ids: chart-<id>, map-<id>, objects-<id>. */
window.renderResultBlocks = function (blocks, BASEMAPS) {
  // Segment palette for pie/doughnut charts. Declared before the render loop
  // runs — a `var` assignment is not hoisted, so defining it later would leave
  // it undefined while the forEach below is already invoking the renderers.
  var PALETTE = ['#4f46e5','#7c73f0','#22c55e','#f59e0b','#ef4444','#06b6d4','#ec4899','#8b5cf6','#10b981','#f97316'];

  // Objects on the map: a plain table via DOM methods (textContent escapes),
  // one row per object, a column per non-text sub-question. Masked objects
  // carry the "<K" label from the server and nothing else.
  function renderObjects(b){
    var holder = document.getElementById('objects-' + b.id);
    if (!holder) return;
    var table = document.createElement('table');
    table.className = 'objects-table';
    var thead = document.createElement('thead'), hr = document.createElement('tr');
    ['', 'Answers'].concat((b.sub_questions || []).map(function(s){ return s.name; })).forEach(function(h){
      var th = document.createElement('th'); th.textContent = h; hr.appendChild(th);
    });
    thead.appendChild(hr); table.appendChild(thead);
    var tbody = document.createElement('tbody');
    (b.rows || []).forEach(function(r){
      var tr = document.createElement('tr');
      if (r.answers.masked) tr.className = 'masked';
      var td = document.createElement('td'); td.textContent = r.title + (r.category ? ' · ' + r.category : ''); tr.appendChild(td);
      td = document.createElement('td'); td.textContent = r.answers.display; tr.appendChild(td);
      (r.subs || []).forEach(function(s){ var c = document.createElement('td'); c.textContent = s.display; tr.appendChild(c); });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    holder.appendChild(table);
  }

  // Map a creator-selected viz to a Chart.js chart type. 'auto' and 'bar'
  // both render as a bar chart; 'table' is handled separately (not Chart.js).
  function chartType(viz){
    if (viz === 'pie') return 'pie';
    if (viz === 'donut') return 'doughnut';
    return 'bar';
  }

  // Build a plain HTML table via safe DOM methods (textContent escapes the
  // creator-supplied labels, so no HTML injection on the public page).
  function renderTable(el, labels, displays){
    var holder = el.parentNode;
    holder.classList.add('is-table');
    var table = document.createElement('table');
    table.className = 'pr-table';
    var tbody = document.createElement('tbody');
    labels.forEach(function(lab, i){
      var tr = document.createElement('tr');
      var tdL = document.createElement('td'); tdL.className = 'lab'; tdL.textContent = lab;
      var tdV = document.createElement('td'); tdV.className = 'val'; tdV.textContent = displays[i];
      tr.appendChild(tdL); tr.appendChild(tdV);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    holder.replaceChildren(table);
  }

  function buildChart(el, type, labels, data, displays, opts){
    opts = opts || {};
    var isPie = (type === 'pie' || type === 'doughnut');
    var colors = isPie ? labels.map(function(_, i){ return PALETTE[i % PALETTE.length]; })
                       : (opts.color || '#4f46e5');
    var cfg = {
      type: type,
      data: { labels: labels, datasets: [{ data: data, backgroundColor: colors, borderRadius: isPie ? 0 : 6 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: isPie },
          tooltip: { callbacks: { label: function(ctx){
            return (displays && displays[ctx.dataIndex] != null)
              ? (labels[ctx.dataIndex] + ': ' + displays[ctx.dataIndex])
              : ctx.formattedValue;
          } } }
        }
      }
    };
    if (!isPie) {
      if (opts.horizontal) {
        cfg.options.indexAxis = 'y';
        cfg.options.scales = { x: { beginAtZero: true, ticks: { precision: 0 } } };
      } else {
        cfg.options.scales = { y: { beginAtZero: true, ticks: { precision: 0 } } };
      }
    }
    new Chart(el, cfg);
  }

  function renderChoiceChart(b){
    var el = document.getElementById('chart-' + b.id); if (!el) return;
    var labels = b.items.map(function(i){ return i.label; });
    // Masked buckets carry value=null; chart shows 0 height but the label
    // text already reads "<K", so the exact count is never revealed.
    var data = b.items.map(function(i){ return i.value == null ? 0 : i.value; });
    var displays = b.items.map(function(i){ return i.display; });
    if (b.viz === 'table') { return renderTable(el, labels, displays); }
    buildChart(el, chartType(b.viz), labels, data, displays, { horizontal: true, color: '#4f46e5' });
  }

  function renderHistogram(b){
    var el = document.getElementById('chart-' + b.id); if (!el || !b.hist_labels) return;
    var displays = b.hist_counts.map(function(c){ return String(c); });
    if (b.viz === 'table') { return renderTable(el, b.hist_labels, displays); }
    buildChart(el, chartType(b.viz), b.hist_labels, b.hist_counts, displays, { horizontal: false, color: '#7c73f0' });
  }

  // A map block (change report-map-views): its own question is the first layer, `b.layers` the
  // other questions its author put on the same map — each a payload of the same shape (`data_type`:
  // a grid of respondent counts per cell, or the marks; `display`: heat | hotspots | squares |
  // marks; `opts`: the view's settings). The first layer is drawn on top. A payload from before has
  // no `display` and no `layers`.
  function renderMap(b){
    var el = document.getElementById('map-' + b.id); if (!el) return;
    var layers = [b].concat(b.layers || []);
    var single = layers.length === 1;
    // Nothing above K anywhere (change data-grid-adaptive): say so instead of an empty map
    // centred on nowhere.
    if (single && !(b.cells && b.cells.features && b.cells.features.length) && b.note) {
      var empty = document.createElement('div');
      empty.className = 'pr-grid-empty';
      empty.style.cssText = 'padding:1.5rem;border:1px dashed #d1d5db;border-radius:8px;color:#4b5563;font-size:.9rem;text-align:center;';
      empty.textContent = b.note;
      el.parentNode.replaceChild(empty, el);
      return;
    }
    var map = L.map(el, { scrollWheelZoom: false });
    el._rpMap = map;      // the report builder reads the view the author framed from it
    var base = BASEMAPS[b.basemap] || BASEMAPS.streets;
    L.tileLayer(base.url, base.opts).addTo(map);
    if (b.scale !== false && L.control.scale) L.control.scale({ imperial: false }).addTo(map);
    // The survey's study area outline (change map-layers-study-area): under every layer, not
    // clickable, never part of the frame the map fits.
    if (b.study_area) {
      L.geoJSON(b.study_area, { interactive: false, style: { color: '#4f46e5', weight: 2, fill: false, opacity: 0.9 } }).addTo(map);
    }

    var groups = {}, bounds = L.latLngBounds([]), soft = false;
    for (var i = layers.length - 1; i >= 0; i--) {          // bottom first
      var layer = layers[i];
      var display = layer.display || (layer.data_type === 'marks' ? 'marks' : 'squares');
      var spots = display === 'hotspots' ? (layer.hotspots || []) : [];
      var opts = layer.opts || {};
      var group = L.featureGroup(), drawn = null;
      if (display === 'heat' || (display === 'hotspots' && opts.shade !== false)) { drawn = renderHeat(map, layer, i); soft = true; }
      else if (display === 'hotspots') { drawn = null; soft = true; }
      else if (layer.data_type === 'marks') { drawn = renderMarks(map, layer, single ? el : null); }
      else { drawn = renderGrid(map, layer, single ? el : null); }
      if (drawn) {
        group.addLayer(drawn);
        try { var box = drawn.getBounds(); if (box.isValid()) bounds.extend(box); } catch (e) { /* an empty layer */ }
      }
      if (spots.length) {
        group.addLayer(renderSpots(layer, spots));
        spots.forEach(function(s){ bounds.extend([s.lat, s.lng]); });
      }
      group.addTo(map);
      groups[i === 0 ? 'main' : layer.id] = group;
    }
    // The basemap steps back, as on the maps of the hand-made reports, so the shading reads.
    if (soft) map.getPane('tilePane').style.filter = 'saturate(.3) brightness(1.05) contrast(.92)';
    bindSpotRows();
    bindLegend(el, map, groups);
    fitMap(map, b, bounds);
  }

  function paintOf(b, fallback){
    return /^#[0-9a-f]{3,8}$/i.test(b.color || '') ? b.color : fallback;
  }

  // The part of the map the author framed, else everything there is to draw.
  function fitMap(map, b, bounds){
    var f = b.frame;
    if (f && f.length === 4) {
      // A hair inside the frame: fitting the exact bounds of a view steps one zoom level out.
      map.fitBounds(L.latLngBounds([f[1], f[0]], [f[3], f[2]]).pad(-0.03));
      return;
    }
    if (bounds.isValid()) { map.fitBounds(bounds.pad(0.1)); } else { map.setView([52.52, 13.405], 11); }
  }

  var SPREAD = { tight: 0.6, medium: 1, wide: 1.6 };
  function strengthOf(opts){ var n = parseInt(opts.strength, 10); return 0.4 + 0.2 * (n >= 1 && n <= 5 ? n : 3); }

  // Shading, as the heat maps of the reports made by hand: the cells that count respondents — or,
  // when the author uses every mark, the marks — drawn on one canvas per layer and blurred, so
  // places many people marked come out darker. Nothing to open.
  function renderHeat(map, b, index){
    var paint = paintOf(b, '#d6336c');
    var opts = b.opts || {};
    var spread = SPREAD[opts.spread] || 1, strength = strengthOf(opts);
    var name = 'rpHeat' + index;
    var pane = map.getPane(name) || map.createPane(name);
    pane.style.zIndex = 410 - index;
    pane.style.pointerEvents = 'none';
    var renderer = L.canvas({ pane: name, padding: 0.3 });
    if (b.data_type === 'marks') {
      pane.style.filter = 'blur(' + Math.round((b.spray ? 3 : 7) * spread) + 'px)';
      return L.geoJSON(b.marks || { features: [] }, {
        pane: name, renderer: renderer, interactive: false,
        pointToLayer: function(feat, latlng){
          return L.circleMarker(latlng, { pane: name, renderer: renderer, interactive: false, stroke: false,
                                          radius: (b.spray ? 5 : 16) * spread, fillColor: paint,
                                          fillOpacity: Math.min(1, (b.spray ? 0.12 : 0.3) * strength) });
        },
        style: function(feat){
          var type = feat && feat.geometry ? feat.geometry.type : '';
          if (type === 'Point' || type === 'MultiPoint') return {};
          // Routes and areas that several people drew overlap, and the overlap is the darker part.
          if (type === 'LineString' || type === 'MultiLineString') {
            return { color: paint, weight: 9 * spread, opacity: Math.min(1, 0.22 * strength), fill: false, lineCap: 'round', lineJoin: 'round' };
          }
          return { stroke: false, fillColor: paint, fillOpacity: Math.min(1, 0.16 * strength) };
        }
      });
    }
    var cells = b.cells || { features: [] };
    var max = b.max || 1;
    var layer = L.geoJSON(cells, {
      pane: name, renderer: renderer, interactive: false,
      style: function(feat){
        var n = (feat.properties || {}).respondents || 0;
        return { stroke: false, fillColor: paint, fillOpacity: Math.min(1, (0.5 + 0.45 * (n / max)) * strength) };
      }
    });
    // The blur follows the zoom: about a third of a cell, so squares melt into each other.
    function soften(){
      var first = cells.features[0];
      var ring = first && first.geometry && first.geometry.coordinates ? first.geometry.coordinates[0] : null;
      if (!ring || ring.length < 3) return;
      var a = map.latLngToLayerPoint([ring[0][1], ring[0][0]]), c = map.latLngToLayerPoint([ring[2][1], ring[2][0]]);
      var px = Math.max(Math.abs(c.x - a.x), Math.abs(c.y - a.y));
      pane.style.filter = 'blur(' + Math.max(2, Math.min(48, Math.round(px * 0.3 * spread))) + 'px)';
    }
    map.on('zoomend load', soften);
    return layer;
  }

  // Numbered hot spots (data.aggregate.hotspots): the busiest is 1 and the largest; the list under
  // the map (reports/_map_spots.html) carries the same numbers, and a click on a row goes there.
  function renderSpots(b, spots){
    var paint = paintOf(b, '#4f46e5');
    var peak = 1, group = L.layerGroup();
    spots.forEach(function(s){ peak = Math.max(peak, s.respondents || 0); });
    spots.slice().reverse().forEach(function(s){
      var size = Math.round(22 + 12 * ((s.respondents || 0) / peak));
      group.addLayer(L.marker([s.lat, s.lng], {
        interactive: false, keyboard: false, zIndexOffset: 1000 - (parseInt(s.rank, 10) || 0),
        icon: L.divIcon({
          className: 'rp-spot-icon', iconSize: [size, size],
          html: '<span class="rp-spot-badge" style="background:' + paint + '">' + (parseInt(s.rank, 10) || '') + '</span>'
        })
      }));
    });
    return group;
  }

  function bindSpotRows(){
    if (window._rpSpotsBound) return;
    window._rpSpotsBound = true;
    document.addEventListener('click', function(e){
      var li = e.target.closest && e.target.closest('.rp-spots li[data-lat]');
      if (!li) return;
      var holder = document.getElementById(li.parentNode.getAttribute('data-map'));
      var m = holder && holder._rpMap;
      if (m) m.setView([parseFloat(li.getAttribute('data-lat')), parseFloat(li.getAttribute('data-lng'))], Math.max(m.getZoom(), 16));
    });
  }

  // The legend under a map of several layers; where the author lets readers, its boxes switch
  // a layer off and on.
  function bindLegend(el, map, groups){
    var legend = el.parentNode ? el.parentNode.querySelector('.rp-legend[data-map="' + el.id + '"]') : null;
    if (!legend) return;
    legend.addEventListener('change', function(e){
      var box = e.target, group = box && box.getAttribute ? groups[box.getAttribute('data-layer')] : null;
      if (!group) return;
      if (box.checked) { group.addTo(map); } else { map.removeLayer(group); }
    });
  }

  function captionOf(el, text){
    if (!el || !el.parentNode) return;
    var cap = document.createElement('div');
    cap.className = 'pr-grid-caption';
    cap.style.cssText = 'font-size:.8rem;color:#6b7280;margin-top:.35rem;';
    cap.textContent = text;
    el.parentNode.insertBefore(cap, el.nextSibling);
  }

  // The marks as respondents placed them: geometry only, nothing to open. `el`: the holder to
  // caption, for a map of this one layer.
  function renderMarks(map, b, el){
    var paint = paintOf(b, '#4f46e5');
    var opts = b.opts || {};
    var k = ({ s: 0.6, m: 1, l: 1.6 })[opts.size] || 1;
    var solid = !!opts.solid;
    var layer = L.geoJSON(b.marks || { features: [] }, {
      interactive: false,
      pointToLayer: function(feat, latlng){
        return L.circleMarker(latlng, { radius: (b.spray ? 2 : 5) * k, stroke: !b.spray, color: '#fff', weight: 1,
                                        fillColor: paint, fillOpacity: solid ? 1 : (b.spray ? 0.35 : 0.75), interactive: false });
      },
      style: function(feat){
        var type = feat && feat.geometry ? feat.geometry.type : '';
        if (type === 'Point' || type === 'MultiPoint') return {};   // pointToLayer styled them
        return { color: paint, weight: 3 * k, opacity: solid ? 1 : 0.6, fillColor: paint, fillOpacity: solid ? 0.5 : 0.12 };
      }
    });
    captionOf(el, (b.count || 0) + ' marks · ' + (b.respondents_total || 0) + ' respondents');
    return layer;
  }

  // Public maps (spec public-aggregates): a server-side grid of respondent counts per cell,
  // cells under K already left out; opacity grows with the count. A cell's popup lists the
  // masked distribution of the creator-selected fields, built with textContent only.
  function renderGrid(map, b, el){
    var cells = b.cells || { features: [] };
    var max = b.max || 1;
    var paint = paintOf(b, '#d6336c');   // the question's colour: the paint respondents used
    var layer = L.geoJSON(cells, {
      style: function(feat){
        var n = (feat.properties || {}).respondents || 0;
        return { stroke: false, fillColor: paint, fillOpacity: 0.15 + 0.6 * (n / max) };
      },
      onEachFeature: function(feat, lyr){
        var props = feat.properties || {};
        var box = document.createElement('div');
        var head = document.createElement('b');
        head.textContent = (props.respondents || 0) + ' respondents';
        box.appendChild(head);
        (props.fields || []).forEach(function(f){
          var row = document.createElement('div');
          var name = document.createElement('span');
          name.style.fontWeight = '600';
          name.textContent = f.name + ': ';
          row.appendChild(name);
          var text = (f.values || []).map(function(v){ return v.label + ' ' + v.display; }).join(', ');
          if (f.mean != null) { text = 'average ' + f.mean; }
          row.appendChild(document.createTextNode(text));
          box.appendChild(row);
        });
        lyr.bindPopup(box);
      }
    });
    captionOf(el, (b.respondents_total || 0) + ' respondents · ' + (b.cell_m ? Math.round(b.cell_m) + ' m cells' : '')
      + (b.note ? ' · ' + b.note : ''));
    return layer;
  }

  (blocks || []).forEach(function(b){
    if (b.block_type === 'chart' && b.data_type === 'choices') { renderChoiceChart(b); }
    else if (b.block_type === 'chart' && b.data_type === 'number') { renderHistogram(b); }
    else if (b.block_type === 'map') { renderMap(b); }
    else if (b.block_type === 'objects') { renderObjects(b); }
  });
};
