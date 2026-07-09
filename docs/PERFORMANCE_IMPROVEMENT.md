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

## Priority Order

1. Add `leaflet.markercluster` — 10 min, prevents map crash at scale
2. Server-side export — unblocks export for real datasets
3. Distinct-value filter dropdowns — better UX, prevents empty result frustration
4. Server-side cluster endpoint — scales map beyond 50k
5. Virtual scrolling — nice-to-have, low priority
