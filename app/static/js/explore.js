/* kvuno Data Explorer — filters, map, table, export */
(function () {
  'use strict';

  var state = {
    page: 1,
    perPage: 50,
    sortCol: null,
    sortDir: null,
  };

  var map = null;
  var markers = null;

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
  var prevBtn = $('page-prev');
  var nextBtn = $('page-next');
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
    return p.toString();
  }

  function fetchData() {
    var q = buildQuery();
    urlFromState();
    // highlight active sort
    document.querySelectorAll('.col-sort').forEach(function (th) {
      th.classList.remove('asc', 'desc');
      if (th.dataset.col === state.sortCol) th.classList.add(state.sortDir || 'asc');
    });
    return fetch('/api/v1/planting-data/?' + q)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        renderTable(data);
        renderMap(data);
        updatePagination(data);
        resultCount.textContent = data.total + ' record' + (data.total !== 1 ? 's' : '');
      })
      .catch(function (err) {
        dataRows.innerHTML = '<tr><td colspan="8" class="text-center text-danger small py-3">' + escHtml(err.message) + '</td></tr>';
      });
  }

  // ── Table ───────────────────────────────────────────────────

  function renderTable(data) {
    var items = data.data || [];
    if (!items.length) {
      dataRows.innerHTML = '<tr><td colspan="8" class="text-center text-muted small py-3">No records match your filters.</td></tr>';
      return;
    }
    var rows = items.map(function (r) {
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
    dataRows.innerHTML = rows;
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

  // ── Pagination ──────────────────────────────────────────────

  function updatePagination(data) {
    pageInfo.textContent = 'Page ' + data.current_page + ' of ' + (data.pages || 1);
    prevBtn.disabled = data.current_page <= 1;
    nextBtn.disabled = data.current_page >= (data.pages || 1);
  }

  function goToPage(page) {
    state.page = page;
    fetchData();
  }

  // ── Export ───────────────────────────────────────────────────

  function exportFormat(fmt) {
    var q = buildQuery();
    // fetch all matching records (no pagination limit)
    var p = new URLSearchParams(q);
    p.set('per_page', 100000);
    p.set('page', 1);
    fetch('/api/v1/planting-data/?' + p.toString())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var items = data.data || [];
        if (!items.length) { alert('No data to export.'); return; }
        var blob, ext;
        if (fmt === 'csv') {
          ext = 'csv';
          var headers = Object.keys(items[0]).filter(function (k) { return k !== 'check_sum' && k !== 'coordinates'; });
          var lines = [headers.join(',')];
          items.forEach(function (row) {
            lines.push(headers.map(function (h) {
              var v = row[h];
              if (v === null || v === undefined) return '';
              v = String(v);
              if (v.indexOf(',') !== -1 || v.indexOf('"') !== -1 || v.indexOf('\n') !== -1) {
                v = '"' + v.replace(/"/g, '""') + '"';
              }
              return v;
            }).join(','));
          });
          blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        } else {
          ext = 'json';
          blob = new Blob([JSON.stringify(items, null, 2)], { type: 'application/json;charset=utf-8;' });
        }
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'kvuno-export.' + ext;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(function (err) { alert('Export failed: ' + err.message); });
  }

  // ── Event wiring ────────────────────────────────────────────

  // Debounced filter input
  var debounceTimer;
  function onFilterInput() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      state.page = 1;
      fetchData();
    }, 350);
  }

  Object.keys(filters).forEach(function (key) {
    filters[key].addEventListener('input', onFilterInput);
  });

  clearBtn.addEventListener('click', function () {
    Object.keys(filters).forEach(function (key) { filters[key].value = ''; });
    state.page = 1;
    fetchData();
  });

  prevBtn.addEventListener('click', function () { if (!prevBtn.disabled) goToPage(state.page - 1); });
  nextBtn.addEventListener('click', function () { if (!nextBtn.disabled) goToPage(state.page + 1); });

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
      state.page = 1;
      fetchData();
    });
  });

  // ── Init ────────────────────────────────────────────────────

  function escHtml(s) {
    if (s === null || s === undefined) return '';
    var d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  paramsFromUrl();
  fetchData();

})();
