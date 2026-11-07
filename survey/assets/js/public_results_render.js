/* The browser renderer of public result payloads (change landing-results, #578).
 * Moved verbatim from the inline script of public_results.html so that /r/<slug>/ and landing
 * pages draw charts, maps and object tables with ONE code path. `blocks` are the payloads of
 * survey/public_results.py::PublicResultsService; `BASEMAPS` is a basemap table
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

  function renderMap(b){
    var el = document.getElementById('map-' + b.id); if (!el) return;
    var map = L.map(el, { scrollWheelZoom: false });
    var base = BASEMAPS[b.basemap] || BASEMAPS.streets;
    L.tileLayer(base.url, base.opts).addTo(map);

    if (b.data_type === 'grid') { return renderGrid(map, b); }

    var fc = b.feature_collection || { features: [] };
    var isHeat = (b.viz === 'heatmap' || b.viz === 'heat');
    // Clusters (spec public-results-page, change cluster-map): nearby points
    // merge into a counted circle that splits on zoom. Without the plugin
    // (CDN blocked) the block falls back to plain markers.
    var isCluster = (b.viz === 'cluster' && typeof L.markerClusterGroup === 'function');
    var pts = [];
    function isPoint(feat){ return !!(feat.geometry && feat.geometry.type === 'Point'); }
    function bindProps(feat, lyr){
      var props = feat.properties || {};
      var keys = Object.keys(props);
      if (keys.length) {
        lyr.bindPopup(keys.map(function(k){ return '<b>' + k + ':</b> ' + props[k]; }).join('<br>'));
      }
    }

    // In heatmap mode, point features become heat intensity only — drawing the
    // individual markers on top (markerPane z-index 600) would completely hide
    // the heat canvas (overlayPane z-index 400). In cluster mode they go into
    // the cluster group below. Non-point geometries always render as shapes.
    var layer = L.geoJSON(fc, {
      filter: function(feat){
        if ((isHeat || isCluster) && isPoint(feat)) return false;
        return true;
      },
      onEachFeature: bindProps
    }).addTo(map);

    var clusters = null;
    if (isCluster) {
      clusters = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 50, chunkedLoading: true });
      clusters.addLayer(L.geoJSON(fc, { filter: isPoint, onEachFeature: bindProps }));
      map.addLayer(clusters);
    }

    // Collect point coordinates for the heat layer and for bounds.
    (fc.features || []).forEach(function(feat){
      if (feat.geometry && feat.geometry.type === 'Point') {
        pts.push([feat.geometry.coordinates[1], feat.geometry.coordinates[0]]);
      }
    });

    if (isHeat && pts.length) {
      L.heatLayer(pts, { radius: 25, blur: 18, minOpacity: 0.35 }).addTo(map);
    }

    try {
      // Heat and cluster modes keep points out of `layer`: widen by them.
      var bounds = layer.getBounds();
      if (pts.length) { bounds = bounds.isValid() ? bounds.extend(L.latLngBounds(pts)) : L.latLngBounds(pts); }
      if (bounds && bounds.isValid()) { map.fitBounds(bounds.pad(0.2)); }
      else { map.setView([52.52, 13.405], 11); }
    } catch (e) { map.setView([52.52, 13.405], 11); }
  }

  // Spray-cloud blocks (spec spraycan-density-views): a server-side grid of
  // respondent counts per cell; opacity grows with the count. No popups, no dots.
  function renderGrid(map, b){
    var cells = b.cells || { features: [] };
    var max = b.max || 1;
    var paint = b.color || '#d6336c';   // the question's colour: the paint respondents used
    var layer = L.geoJSON(cells, {
      style: function(feat){
        var n = (feat.properties || {}).respondents || 0;
        return { stroke: false, fillColor: paint, fillOpacity: 0.15 + 0.6 * (n / max) };
      }
    }).addTo(map);
    try {
      var bounds = layer.getBounds();
      if (bounds.isValid()) { map.fitBounds(bounds.pad(0.1)); } else { map.setView([52.52, 13.405], 11); }
    } catch (e) { map.setView([52.52, 13.405], 11); }
    var el = document.getElementById('map-' + b.id);
    if (el && el.parentNode) {
      var cap = document.createElement('div');
      cap.className = 'pr-grid-caption';
      cap.style.cssText = 'font-size:.8rem;color:#6b7280;margin-top:.35rem;';
      cap.textContent = (b.respondents_total || 0) + ' respondents · ' + (b.cell_m ? Math.round(b.cell_m) + ' m cells' : '');
      el.parentNode.insertBefore(cap, el.nextSibling);
    }
  }

  (blocks || []).forEach(function(b){
    if (b.block_type === 'chart' && b.data_type === 'choices') { renderChoiceChart(b); }
    else if (b.block_type === 'chart' && b.data_type === 'number') { renderHistogram(b); }
    else if (b.block_type === 'map') { renderMap(b); }
    else if (b.block_type === 'objects') { renderObjects(b); }
  });
};
