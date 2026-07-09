/* kvuno Data Explorer — filters, map, table, export */
(function () {
  'use strict';

  var state = {
    page: 1,
    perPage: 200,
    sortCol: null,
    sortDir: null,
  };

  var totalRecords = 0;
  var loading = false;
  var hasMore = true;
  var scrollObs = null;

  var map = null;
  var markers = null;
  var heat = null;
  var heatVisible = false;
  var clusterLayer = null;
  var clusterVisible = false;

  // ── DOM refs ────────────────────────────────────────────────

  var $ = function (id) { return document.getElementById(id); };

  var filters = {
    country: $('f-country'),
    province: $('f-province'),
    variety: $('f-variety'),
    season: $('f-season'),
    date: $('f-date'),
    option: $('f-option'),
    radius: $('f-radius'),
    lon: $('f-lon'),
    lat: $('f-lat'),
  };

  var dataRows = $('data-rows');
  var pageInfo = $('page-info');
  var resultCount = $('result-count');
  var scrollStatus = $('scroll-status');
  var tableWrap = document.querySelector('.table-wrap');
  var clearBtn = $('clear-filters');
  var exportCsv = $('export-csv');
  var exportJson = $('export-json');

  // ── URL <-> state ───────────────────────────────────────────

  function paramsFromUrl() {
    var p = new URLSearchParams(location.search);
    filters.country.value = p.get('country') || '';
    filters.province.value = p.get('province') || '';
    filters.variety.value = p.get('variety') || '';
    filters.season.value = p.get('season_type') || '';
    filters.date.value = p.get('opt_date') || '';
    filters.option.value = p.get('planting_option') || '';
    filters.radius.value = p.get('radius') || '';
    filters.lon.value = p.get('lon') || '';
    filters.lat.value = p.get('lat') || '';
    state.page = parseInt(p.get('page')) || 1;
    state.sortCol = p.get('sort_col') || null;
    state.sortDir = p.get('sort_dir') || null;
  }

  function urlFromState() {
    var p = new URLSearchParams();
    forEachFilter(function (key, el) {
      if (el.value) p.set(key, el.value);
    });
    if (state.page > 1) p.set('page', state.page);
    if (state.sortCol) p.set('sort_col', state.sortCol);
    if (state.sortDir) p.set('sort_dir', state.sortDir);
    var q = p.toString();
    var url = location.pathname + (q ? '?' + q : '');
    history.replaceState(null, '', url);
  }

  function forEachFilter(fn) {
    var map = {
      country: 'country', province: 'province', variety: 'variety',
      season: 'season_type', date: 'opt_date', option: 'planting_option',
      radius: 'radius', lon: 'lon', lat: 'lat',
    };
    Object.keys(map).forEach(function (key) {
      fn(map[key], filters[key]);
    });
  }

  // ── Data fetching ───────────────────────────────────────────

  function buildQuery() {
    var p = new URLSearchParams();
    p.set('page', state.page);
    p.set('per_page', state.perPage);
    forEachFilter(function (key, el) {
      if (el.value) p.set(key, el.value);
    });
    // spatial: combine lon+lat into coordinates
    if (filters.lon.value && filters.lat.value) {
      p.set('coordinates', filters.lon.value + ',' + filters.lat.value);
    }
    if (state.sortCol) p.set('sort_col', state.sortCol);
    if (state.sortDir) p.set('sort_dir', state.sortDir);
    return p.toString();
  }

  function fetchData(reset) {
    if (loading) return;
    if (!reset && !hasMore) return;
    loading = true;
    if (reset) {
      state.page = 1;
      hasMore = true;
      totalRecords = 0;
      dataRows.innerHTML = '';
    }
    scrollStatus.textContent = 'Loading…';

    var q = buildQuery();
    urlFromState();
    // highlight active sort
    document.querySelectorAll('.col-sort').forEach(function (th) {
      th.classList.remove('asc', 'desc');
      if (th.dataset.col === state.sortCol) th.classList.add(state.sortDir || 'asc');
    });
    return fetch('/api/v1/planting-data?' + q)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        totalRecords = data.total;
        hasMore = data.current_page < data.pages;
        renderTable(data.data, !reset);
        renderMap(data);
        resultCount.textContent = data.total + ' record' + (data.total !== 1 ? 's' : '');
        pageInfo.textContent = 'Showing ' + dataRows.children.length + ' of ' + data.total;
        state.page = data.current_page + 1;
        updateScrollSentinel();
        loading = false;
      })
      .catch(function (err) {
        if (reset || !dataRows.children.length) {
          dataRows.innerHTML = '<tr><td colspan="8" class="text-center text-danger small py-3">' + escHtml(err.message) + '</td></tr>';
        }
        loading = false;
      });
  }

  function updateScrollSentinel() {
    disconnectObs();
    // remove old sentinel
    var old = dataRows.querySelector('.scroll-sentinel');
    if (old) old.remove();

    if (!hasMore) {
      scrollStatus.textContent = '\u2713 All ' + totalRecords + ' records loaded';
      return;
    }
    scrollStatus.textContent = 'Scroll for more…';
    var tr = document.createElement('tr');
    tr.className = 'scroll-sentinel';
    tr.innerHTML = '<td colspan="8" class="text-center small text-muted py-2"><div class="spinner-border spinner-border-sm me-1" role="status"></div> Loading…</td>';
    dataRows.appendChild(tr);
    scrollObs = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting && hasMore && !loading) {
        fetchData(false);
      }
    }, { root: tableWrap, rootMargin: '200px' });
    scrollObs.observe(tr);
  }

  function disconnectObs() {
    if (scrollObs) { scrollObs.disconnect(); scrollObs = null; }
  }

  // ── Table ───────────────────────────────────────────────────

  function renderTable(items, append) {
    items = items || [];
    if (!items.length && !append) {
      dataRows.innerHTML = '<tr><td colspan="8" class="text-center text-muted small py-3">No records match your filters.</td></tr>';
      disconnectObs();
      scrollStatus.textContent = '';
      return;
    }
    var html = items.map(function (r) {
      return '<tr>'
        + '<td>' + escHtml(r.country) + '</td>'
        + '<td>' + escHtml(r.province) + '</td>'
        + '<td>' + escHtml(r.variety) + '</td>'
        + '<td>' + escHtml(r.lon) + '</td>'
        + '<td>' + escHtml(r.lat) + '</td>'
        + '<td>' + escHtml(r.season_type) + '</td>'
        + '<td>' + escHtml(r.opt_date) + '</td>'
        + '<td>' + escHtml(r.planting_option) + '</td>'
        + '</tr>';
    }).join('');
    if (append) {
      dataRows.insertAdjacentHTML('beforeend', html);
    } else {
      dataRows.innerHTML = html;
    }
  }

  // ── Map ──────────────────────────────────────────────────────

  function initMap() {
    if (map) return;
    map = L.map('explore-map').setView([-12, 28], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 18,
    }).addTo(map);
    markers = L.markerClusterGroup ? null : L.layerGroup();
    // If leaflet.markercluster is loaded, use clustering
    if (L.markerClusterGroup) {
      markers = L.markerClusterGroup({ chunkedLoading: true });
    } else {
      markers = L.layerGroup();
    }
    map.addLayer(markers);
  }

  function renderMap(data) {
    initMap();
    if (heatVisible || clusterVisible) return;
    markers.clearLayers();
    var items = data.data || [];
    if (!items.length) return;

    var bounds = [];
    items.forEach(function (r) {
      var lat = parseFloat(r.lat);
      var lon = parseFloat(r.lon);
      if (isNaN(lat) || isNaN(lon)) return;
      var m = L.circleMarker([lat, lon], {
        radius: 5, fillColor: '#1976d2', color: '#fff',
        weight: 1, fillOpacity: 0.8,
      });
      var label = (r.country || '') + ' - ' + (r.variety || '')
        + '<br/>Date: ' + (r.opt_date || '')
        + '<br/>Option: ' + (r.planting_option || '');
      m.bindTooltip(label);
      markers.addLayer(m);
      bounds.push([lat, lon]);
    });

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [20, 20], maxZoom: 12 });
    }
  }

  // ── Export ───────────────────────────────────────────────────

  function exportFormat(fmt) {
    var q = buildQuery();
    var p = new URLSearchParams(q);
    p.set('format', fmt);
    var url = '/api/v1/planting-data/export?' + p.toString();
    var a = document.createElement('a');
    a.href = url;
    a.download = 'kvuno-export.' + fmt;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // ── Event wiring ────────────────────────────────────────────

  // Debounced filter input
  var debounceTimer;
  function onFilterInput() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      fetchData(true);
    }, 350);
  }

  var selectFilters = { country: 1, province: 1, variety: 1, season: 1 };
  Object.keys(filters).forEach(function (key) {
    filters[key].addEventListener(selectFilters[key] ? 'change' : 'input', onFilterInput);
  });

  clearBtn.addEventListener('click', function () {
    Object.keys(filters).forEach(function (key) { filters[key].value = ''; });
    fetchData(true);
  });

  exportCsv.addEventListener('click', function () { exportFormat('csv'); });
  exportJson.addEventListener('click', function () { exportFormat('json'); });

  // Column sorting
  document.querySelectorAll('.col-sort').forEach(function (th) {
    th.addEventListener('click', function () {
      var col = this.dataset.col;
      if (state.sortCol === col) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortCol = col;
        state.sortDir = 'asc';
      }
      fetchData(true);
    });
  });

  // ── Heatmap toggle ──────────────────────────────────────────

  var heatmapBtn = $('toggle-heatmap');

  heatmapBtn.addEventListener('click', function () {
    heatVisible = !heatVisible;
    heatmapBtn.classList.toggle('active', heatVisible);
    heatmapBtn.innerHTML = heatVisible
      ? '<i class="bi bi-fire"></i> Points'
      : '<i class="bi bi-fire"></i> Heatmap';

    if (heatVisible) {
      if (markers) map.removeLayer(markers);
      showHeatmap();
    } else {
      if (heat) map.removeLayer(heat);
      if (markers) map.addLayer(markers);
    }
  });

  function showHeatmap() {
    var p = new URLSearchParams();
    forEachFilter(function (key, el) {
      if (el.value) p.set(key, el.value);
    });
    if (filters.lon.value && filters.lat.value) {
      p.set('coordinates', filters.lon.value + ',' + filters.lat.value);
    }

    fetch('/api/v1/planting-data/coordinates?' + p.toString())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        var points = (data.coordinates || []).map(function (c) {
          return [c.lat, c.lon, 1];
        });
        if (!points.length) { showToast('No coordinate data to show.', 'warning'); return; }
        if (heat) map.removeLayer(heat);
        heat = L.heatLayer(points, {
          radius: 20, blur: 15, maxZoom: 10,
          gradient: { 0.4: '#1976d2', 0.6: '#ff9800', 0.8: '#f44336' },
        }).addTo(map);
        map.fitBounds(points.map(function (p) { return [p[0], p[1]]; }), { padding: [20, 20], maxZoom: 10 });
      })
      .catch(function (err) { showToast('Heatmap error: ' + err.message, 'danger'); });
  }

  // ── Clusters toggle ─────────────────────────────────────────

  var clusterBtn = $('toggle-clusters');

  clusterBtn.addEventListener('click', function () {
    if (heatVisible) {
      heatVisible = false;
      heatmapBtn.classList.remove('active');
      heatmapBtn.innerHTML = '<i class="bi bi-fire"></i> Heatmap';
      if (heat) map.removeLayer(heat);
    }

    clusterVisible = !clusterVisible;
    clusterBtn.classList.toggle('active', clusterVisible);
    clusterBtn.innerHTML = clusterVisible
      ? '<i class="bi bi-diagram-3"></i> Points'
      : '<i class="bi bi-diagram-3"></i> Clusters';

    if (clusterVisible) {
      if (markers) map.removeLayer(markers);
      showClusters();
    } else {
      if (clusterLayer) map.removeLayer(clusterLayer);
      if (markers) map.addLayer(markers);
    }
  });

  function showClusters() {
    var bounds = map.getBounds();
    var zoom = map.getZoom();
    var p = new URLSearchParams();
    p.set('zoom', zoom);
    p.set('ne_lat', bounds.getNorth());
    p.set('ne_lng', bounds.getEast());
    p.set('sw_lat', bounds.getSouth());
    p.set('sw_lng', bounds.getWest());
    forEachFilter(function (key, el) {
      if (el.value) p.set(key, el.value);
    });

    fetch('/api/v1/planting-data/clusters?' + p.toString())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        var items = data.clusters || [];
        if (!items.length) { showToast('No cluster data.', 'warning'); return; }
        if (clusterLayer) map.removeLayer(clusterLayer);
        clusterLayer = L.layerGroup();

        var maxCount = items.reduce(function (m, c) { return Math.max(m, c.count); }, 1);
        var boundsArr = [];
        items.forEach(function (c) {
          var lat = parseFloat(c.lat);
          var lon = parseFloat(c.lon);
          if (isNaN(lat) || isNaN(lon)) return;
          var r = Math.max(4, Math.min(20, 4 + (c.count / maxCount) * 16));
          var fill = c.count > maxCount * 0.5 ? '#e53935'
                   : c.count > maxCount * 0.2 ? '#ff9800'
                   : '#1976d2';
          var m = L.circleMarker([lat, lon], {
            radius: r, fillColor: fill, color: '#fff',
            weight: 1.5, fillOpacity: 0.75,
          });
          m.bindTooltip(c.count + ' record' + (c.count !== 1 ? 's' : ''));
          clusterLayer.addLayer(m);
          boundsArr.push([lat, lon]);
        });
        map.addLayer(clusterLayer);
        if (boundsArr.length) {
          map.fitBounds(boundsArr, { padding: [20, 20], maxZoom: zoom + 1 });
        }
      })
      .catch(function (err) { showToast('Clusters error: ' + err.message, 'danger'); });
  }

  // ── Load filter options ─────────────────────────────────────

  function loadFilterOptions() {
    fetch('/api/v1/planting-data/filters')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) return;
        var map = { country: 'f-country', province: 'f-province', variety: 'f-variety', season_type: 'f-season' };
        Object.keys(map).forEach(function (key) {
          var sel = document.getElementById(map[key]);
          if (!sel) return;
          var vals = data[key] || [];
          sel.innerHTML = '<option value="">All</option>';
          vals.forEach(function (v) {
            var opt = document.createElement('option');
            opt.value = v;
            opt.textContent = v;
            sel.appendChild(opt);
          });
        });
      })
      .catch(function () {});
  }

  // ── Init ────────────────────────────────────────────────────

  function escHtml(s) {
    if (s === null || s === undefined) return '';
    var d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  loadFilterOptions();
  paramsFromUrl();
  fetchData(true);

})();
