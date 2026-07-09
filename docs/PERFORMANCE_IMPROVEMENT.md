# Performance Improvements — Data Explorer

Based on the DESIGN.md mockup (~42k records expected) and current implementation analysis, the explore page has scaling bottlenecks. This document outlines the issues and recommended solutions.

## Current Architecture (Phase 2)

| Component | Implementation | Scaling Limit |
|---|---|---|
| **Table** | Server-paginated (50/page) via `/api/v1/planting-data?page=N&per_page=50` | Good — pagination is inherently scalable |
| **Map** | All records from current page rendered as individual `L.circleMarker` | Limited to ~500 markers before browser lag |
| **Sort** | `sort_col`/`sort_dir` sent to API, sorted by SQL | Good — database handles sorting |
| **Filters** | Text inputs with 350ms debounced `fetch` | OK — but user must guess valid values |
| **Export** | Fetches `per_page=100000`, generates CSV/JSON client-side in JS | **Will crash the browser** on datasets >10k rows |
| **URL state** | Query params in `history.replaceState` | Good — shareable, bookmarkable |
| **Map clustering** | Not installed — `leaflet.markercluster` not in `package.json` | Fallback to `L.layerGroup` — all markers draw individually |

## Recommendations

### 1. Add Leaflet.markercluster (high impact, low effort)

Install the package and load it in the template. This groups nearby points into count bubbles at low zoom levels and only renders individual markers when zoomed in. Handles 50k+ points on the client without issue.

**Effort:** ~10 min

**Changes:**
- `pnpm add leaflet.markercluster`
- Add to `explore.html`: `<script src="{{ url_for('npm_serve', filename='leaflet.markercluster/dist/leaflet.markercluster.js') }}">`
- The JS at `explore.js:154-160` already conditionally uses `L.markerClusterGroup` — it will activate automatically once the library is loaded.

### 2. Server-side Export Endpoint (high impact, medium effort)

Current client-side export (`per_page=100000`) loads all matching records into browser memory, then generates a blob. For 42k+ records with 13 columns, this can consume 50+ MB of JS heap and freeze the tab.

Replace with a streaming server endpoint:

```
GET /api/v1/planting-data/export?format=csv&country=...
GET /api/v1/planting-data/export?format=json&country=...
```

The server streams the response directly, optionally with `Content-Disposition: attachment`.

**Effort:** ~2-3h

### 3. Distinct-Value Filter Dropdowns (medium impact, medium effort)

Text inputs for country/variety/season are frustrating — users don't know what values exist. Add an endpoint returning distinct values for filterable columns:

```
GET /api/v1/planting-data/filters
→ { "countries": ["Zambia","Kenya",...], "varieties": ["H614","Soybean",...], ... }
```

Populate `<select>` elements from these on page load. All columns have DB indexes, so `SELECT DISTINCT` queries are cheap.

**Effort:** ~2-3h

### 4. Server-side Map Clusters (medium impact, higher effort)

For datasets beyond 50k points, even markercluster can struggle. Add a spatial aggregation endpoint that returns pre-computed clusters:

```
GET /api/v1/planting-data/clusters?zoom=5&ne_lat=...&ne_lng=...&sw_lat=...&sw_lng=...
→ { "clusters": [{ "lat": -12.5, "lng": 28.3, "count": 142 }, ...] }
```

The repo already has GiST indexes on `coordinates` — spatial queries with `ST_SnapToGrid` or `ST_ClusterDBSCAN` are fast.

**Effort:** ~4-6h

### 5. Virtual Scrolling Table (low impact, higher effort)

Replacing pagination buttons with a virtualized/infinite-scroll table improves browsing experience. However, pagination is fine for data scientist users who compare pages and share filtered URLs. Low priority.

**Effort:** ~4-6h

## Existing Strengths (no change needed)

| Feature | Why it's fine |
|---|---|
| **Server-side pagination** | SQL `LIMIT/OFFSET` with indexes is efficient at any scale |
| **Server-side sort** | Sorting in the database is always faster than sorting in JS |
| **Debounced filter input** | Prevents request storms on every keystroke |
| **URL-persisted state** | Bookmarkable, shareable — important for data scientists |
| **Database indexes** | 11 indexes covering all filter/sort columns — well indexed |
| **conditional markerCluster code** | JS already detects `L.markerClusterGroup` — just needs the library loaded |

## Phased Implementation Plan

### Phase 1 — Map Clustering (1 commit, ~10 min) ✅
- [✅] Install `leaflet.markercluster` via pnpm
- [✅] Load script in `explore.html`
- [✅] Auto-activated — JS already conditionally uses `L.markerClusterGroup`

### Phase 2 — Server-side Export (1 commit, ~2-3h) ✅
- [✅] `GET /api/v1/planting-data/export?format=csv|json` — streams filtered results with `yield_per(500)`
- [✅] Replaced client-side Blob export with server streaming download
- [✅] CSV uses csv.writer for proper quoting, JSON streams as newline-delimited array

### Phase 3 — Distinct-Value Filter Dropdowns (1 commit, ~2-3h) ✅
- [✅] `GET /api/v1/planting-data/filters` — returns distinct values per column
- [✅] Replaced text inputs with `<select>` for country, province, variety, season
- [✅] Populated on page load; `change` event for selects, `input` for text fields

### Phase 4 — Server-side Map Clusters (1 commit, ~4-6h) ✅
- [✅] `GET /api/v1/planting-data/clusters?zoom=N&bounds=...` — spatial aggregation with `ST_SnapToGrid`
- [✅] Clusters toggle button on explore page — renders sized/colored circles by density

### Phase 5 — Infinite Scroll Table (1 commit, ~4-6h) ✅
- [✅] Replaced prev/next pagination buttons with intersection-observer-driven infinite scroll
- [✅] Table appends rows as user scrolls; scroll sentinel triggers next page fetch
- [✅] Filters/sort resets to page 1 and clears table; URL page state preserved for shareability
- [✅] Increased default `perPage` to 200 for fewer round trips
