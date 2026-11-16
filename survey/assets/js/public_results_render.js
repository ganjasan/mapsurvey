/* The browser renderer of public result payloads (change landing-results, #578).
 * Moved verbatim from the inline script of public_results.html so that /r/<slug>/ and site
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
    // Nothing above K anywhere (change data-grid-adaptive): say so instead of an empty map
    // centred on nowhere.
    if (!(b.cells && b.cells.features && b.cells.features.length) && b.note) {
      var empty = document.createElement('div');
      empty.className = 'pr-grid-empty';
      empty.style.cssText = 'padding:1.5rem;border:1px dashed #d1d5db;border-radius:8px;color:#4b5563;font-size:.9rem;text-align:center;';
      empty.textContent = b.note;
      el.parentNode.replaceChild(empty, el);
      return;
    }
    var map = L.map(el, { scrollWheelZoom: false });
    var base = BASEMAPS[b.basemap] || BASEMAPS.streets;
    L.tileLayer(base.url, base.opts).addTo(map);

    // Every public map is a grid of respondent counts per cell (change data-aggregate):
    // the payload carries no answer geometry, so there is nothing else to draw.
    renderGrid(map, b);
  }

  // Public maps (spec public-aggregates): a server-side grid of respondent counts per cell,
  // cells under K already left out; opacity grows with the count. A cell's popup lists the
  // masked distribution of the creator-selected fields, built with textContent only.
  function renderGrid(map, b){
    var cells = b.cells || { features: [] };
    var max = b.max || 1;
    var paint = b.color || '#d6336c';   // the question's colour: the paint respondents used
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
      cap.textContent = (b.respondents_total || 0) + ' respondents · ' + (b.cell_m ? Math.round(b.cell_m) + ' m cells' : '')
        + (b.note ? ' · ' + b.note : '');
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
