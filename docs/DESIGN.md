# UI/UX Design Plan — kvuno

## Target Users

**Primary:** Data scientists at CGIAR / AgWise who ingest, validate, and serve
agricultural planting-recommendation data (RDS/Parquet files with spatial crop
information).

**Secondary:** API consumers building applications on top of the planting data.

### User goals

| Goal | Frequency | Current UX |
|------|-----------|------------|
| Upload RDS/Parquet files | Daily/weekly | ✅ Upload page with drag-drop + column mapping |
| Preview data before ingestion | Every upload | ❌ Only column names shown, no row preview |
| Monitor processing status | Per upload | ✅ Jobs page with live SSE updates |
| Explore / query ingested data | Daily | ❌ No UI — must use raw API + curl/Postman |
| Filter by country, variety, date | Daily | ❌ No filter UI |
| View data on a map | Weekly | ❌ No spatial visualization |
| Export data for offline analysis | Weekly | ❌ No CSV/Parquet download |
| Understand data quality | Weekly | ❌ No conflict/duplicate dashboard |
| Understand data quality | Weekly | ✅ Quality dashboard with conflicts, duplicates, coverage stats |
| Test API queries interactively | Monthly | ❌ Swagger doc but no live query builder |

---

## Current UI Audit

### Page: Upload (`/ui/upload`)

**What exists:**
- Drag-drop zone with Resumable.js chunked upload
- Column mapping UI (auto-match + manual select)
- Processing trigger

**Gaps:**
- No row preview after upload — shows column names only
- No sample data visible before committing to processing
- Uploads one file at a time (Resumable.js `maxFiles: 1`)
- No per-column type information
- No way to re-map or correct after submission

### Page: Jobs (`/ui/jobs`)

**What exists:**
- SSE live-updating table with status, progress bar, timestamps
- Highlight scroll from upload redirect

**Gaps:**
- No sorting/filtering of job list
- No per-job detail view (logs, row count, timing)
- No retry action for failed jobs
- No history beyond what's in `.progress.json` files


### Page: Quality (`/ui/quality`)

**What exists (Phase 3):**
- Summary stat cards (total records, conflicts, files, spatial coverage %)
- Paginated conflicts table with country/source/search filters
- Duplicates viewer grouped by unique record key
- Source breakdown with bar visualization
- Spatial coverage heatmap on explore page

**Gaps:**
- No per-job conflict detail linking back to the source file
- No data quality trend/history over time
- No automated quality checks (null counts, outlier detection)

---

## Proposed Design

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ [Logo] kvuno                [Upload] [Jobs] [Explore]   │  ← nav
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │                                                 │   │
│   │           Page content via named blocks          │   │
│   │                                                 │   │
│   └─────────────────────────────────────────────────┘   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  kvuno · AgWise · CGIAR                                 │  ← footer
└─────────────────────────────────────────────────────────┘
```

### Page 1: Upload (refined)

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: Select file(s)                                  │
│  ┌───────────────────────────────────────────────────┐   │
│  │  Drop .rds or .parquet files here                  │   │
│  │  or click to browse           [Browse]             │   │
│  └───────────────────────────────────────────────────┘   │
│  [file1.rds ──────────────────────────────────── 100%]   │  ← per-file
│  [file2.parquet ────────────────────────────────── 72%]   │     progress
│                                                         │
│  ── After upload complete ──                             │
│  Step 2: Preview & Map Columns                           │
│  ┌──────────┬──────────────┬──────────┬────────────────┐ │
│  │ File col  │ Sample val   │ Type      │ DB column      │ │
│  ├──────────┼──────────────┼──────────┼────────────────┤ │
│  │ Variety  │ H614         │ string   │ variety      ▼ │ │
│  │ LAT      │ -1.29        │ float    │ lat          ▼ │ │
│  │ LON      │ 36.82        │ float    │ lon          ▼ │ │
│  │ ...      │              │          │                │ │
│  └──────────┴──────────────┴──────────┴────────────────┘ │
│                                         [Process files]  │
└─────────────────────────────────────────────────────────┘
```

**Key improvements:**
- Multiple file upload with per-file progress
- Sample data preview (first 5 rows from the file)
- Type inference from file columns
- Batch column mapping across multiple files

### Page 2: Jobs (refined)

```
┌─────────────────────────────────────────────────────────┐
│  [All] [Completed] [Processing] [Failed]   [Search...]  │  ← filters
├─────────────────────────────────────────────────────────┤
│  Summary: 12 completed  3 processing  1 failed  16 total │
├─────────────────────────────────────────────────────────┤
│  File      │ Status      │ Rows    │ Duration │ Actions │
│  ─────────────────────────────────────────────────────── │
│  data.rds  │ ✅ Completed │ 42,195  │ 12.3s    │ [View]  │
│  field.par │ 🔄 Processing│ 18,200  │ 5.1s     │ -       │
│  old.rds   │ ❌ Failed    │ -       │ 0.4s     │ [Retry] │
│  ...       │             │         │          │         │
└─────────────────────────────────────────────────────────┘
```

**Improvements:**
- Status filter tabs
- Search by filename
- Duration column
- Retry action for failed jobs
- View detail (expand to see logs, conflicts, row sample)

### Page 3: Explore (NEW)

```
┌─────────────────────────────────────────────────────────┐
│  Filters                              [Export ▼] [Clear]│
│  ┌────────┬──────────────────────────────────────────┐  │
│  │ Country│ [Zambia                ▼]   [+ Add filter]│  │
│  │ Variety│ [Soybean               ▼]                │  │
│  │ Lat    │ [min] — [max]                             │  │
│  │ Lng    │ [min] — [max]                             │  │
│  │ Radius │ Lon: [36.82] Lat: [-1.29] Rad: [50km]    │  │
│  └────────┴──────────────────────────────────────────┘  │
│                                                         │
│  ┌── Map ────────────────────────────────────────────┐  │
│  │                                                     │  │
│  │        🗺  Leaflet / MapLibre GL                    │  │
│  │        (clustered point layer)                      │  │
│  │                                                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                         │
│  Showing 1–25 of 42,195 records              [JSON] [CSV]│
│  ┌──────┬─────────┬────────┬──────┬────────┬──────────┐ │
│  │ ID   │ Country │ Variety│ Lon  │ Lat    │ Opt date │ │
│  ├──────┼─────────┼────────┼──────┼────────┼──────────┤ │
│  │ 1    │ Zambia  │ Soybean│ 25.9 │ -17.85 │2024-11-15│ │
│  │ 2    │ Zambia  │ Soybean│ 26.1 │ -17.92 │2024-11-20│ │
│  │ ...  │         │        │      │        │          │ │
│  └──────┴─────────┴────────┴──────┴────────┴──────────┘ │
│                                            [← Prev] [1] [2] [3] … [Next →]│
└─────────────────────────────────────────────────────────┘
```

**Key features:**
- **Interactive filters** — country, variety, season, date range, spatial bounding box
- **Map view** — Leaflet/MapLibre with clustered points, click for detail popup
- **Data table** — sortable, paginated, with column visibility toggles
- **Export** — download filtered results as CSV, JSON, GeoJSON, Parquet
- **Share** — copy shareable URL with filter state

### Page 4: Data Quality Dashboard (future)

```
┌─────────────────────────────────────────────────────────┐
│  Data Quality Overview                                   │
├─────────────────────────────────────────────────────────┤
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────────┐  │
│  │ 42,195  │ │ 12     │ │ 3      │ │ 2.1M             │  │
│  │ records │ │ files  │ │ confs  │ │ spatial coverage │  │
│  └────────┘ └────────┘ └────────┘ └──────────────────┘  │
│                                                         │
│  Conflicts by country:                                   │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Zambia    ████████████████████ 156                   │ │
│  │ Kenya     ████████████         89                    │ │
│  │ Malawi    ██████              42                    │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Technology Recommendations

| Concern | Choice | Reason |
|---------|--------|--------|
| CSS framework | Bootstrap 5.3 (pnpm) | Already in use, good for data-heavy UIs |
| Icons | Bootstrap Icons | Lightweight, no extra dependency |
| Map | Leaflet + leaflet.markercluster | Lightweight, no API key needed; markercluster handles 50k+ points |
| Charts | Chart.js | Simple, good for dashboards |
| Tables | Bootstrap table or simple HTML | No need for DataTables complexity |
| Export CSV | Server streaming endpoint (recommended for scale) | Client-side Blob works <10k rows only; server stream required at scale |
| State in URL | `URLSearchParams` for filter persistence | Shareable URLs |
| Build tool | None — keep as static JS served by Flask | Avoids JS build step complexity |

Data scientists are not frontend engineers — the UI should be:
- **Server-rendered** (Jinja) where possible for initial page load
- **Progressive enhancement** with vanilla JS for interactivity
- **No SPA framework** — keeps the stack simple and maintainable

---

## Phasing

### Phase 1 — Enhance existing pages ✅
- ✅ Base layout with Jinja inheritance
- ✅ url_for for all assets
- ✅ CDN → local pnpm assets
- ✅ Multi-file upload with per-file progress
- ✅ Row preview (sample values) in column mapping
- ✅ Job detail modal with retry action
- ✅ Status filter tabs and filename search on Jobs page

### Phase 2 — Data Explorer ✅
- ✅ New route: `/ui/explore`
- ✅ Filter form (country, province, variety, season, date, option, spatial radius)
- ✅ Paginated data table with column sort
- ✅ CSV / JSON export of filtered results
- ✅ Map view with Leaflet (clustered circle markers)
- ✅ Shareable URL with query params (filters, page, sort persisted)

**Phase 2 caveats (tracked in [`PERFORMANCE_IMPROVEMENT.md`](./PERFORMANCE_IMPROVEMENT.md)):**
- ⚠️ `leaflet.markercluster` is NOT in `package.json` — map falls back to unclustered `L.layerGroup`, which will freeze the browser beyond ~500 points
- ⚠️ Export uses client-side Blob (`per_page=100000`) — will crash the tab on datasets >10k rows
- ⚠️ Filter inputs are plain text fields — users must guess valid country/variety/season values

### Phase 3 — Data Quality ✅
- ✅ Conflicts dashboard (`/ui/quality`) with stat cards, paginated conflict table, source breakdown, country grouping
- ✅ Per-file processing stats (summary cards: total records, conflicts, files, spatial coverage %)
- ✅ Spatial coverage heatmap (Leaflet.heat overlay toggle on explore page)
- ✅ Duplicate detection viewer (grouped by unique key on Quality > Duplicates tab)

---

## Routes Map (proposed)

```
GET  /                    → redirect → /ui/jobs
GET  /ui/upload           → upload page
GET  /ui/jobs             → jobs page
GET  /ui/jobs/data        → JSON: job list
GET  /ui/jobs/events      → SSE: live updates
GET  /ui/explore          → data explorer page
GET  /ui/quality          → data quality dashboard
GET  /api/v1/planting-data      → JSON: filtered data
GET  /api/v1/planting-data/coordinates  → JSON: lat/lon pairs for heatmap
GET  /api/v1/quality/stats       → JSON: summary statistics
GET  /api/v1/quality/conflicts   → JSON: paginated conflict list
GET  /api/v1/planting-data/export  → CSV/Parquet (future)
```

---

## Design Principles

1. **Data scientists are not frontend devs** — the UI must be intuitive, self-documenting, and require zero configuration.
2. **Progressive disclosure** — show simple filters first, advanced options on expand.
3. **Feedback on every action** — loading states, progress bars, success/error messages.
4. **Shareable state** — every filter configuration should be encoded in the URL.
5. **Keyboard-friendly** — tab through filters, enter to search.
6. **Mobile-conscious** — data tables scroll horizontally, maps stack vertically.
7. **No page reload for data actions** — filters, pagination, and export should be JS-driven for responsiveness.
