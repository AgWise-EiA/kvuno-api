# Data Flow

This document describes the two main data flows in KVuno API: **ingestion** (RDS files into the database) and **serving** (database records through the REST API).

---

## 1. Ingestion Flow — RDS File Processing

RDS (R Data Serialization) files containing crop planting data are either placed in `static/data/` directly or downloaded from remote sources (configured via `REMOTE_RDS_URLS` in `.env`), then processed by `housekeeping.py`.

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Remote server   │────▶│  housekeeping.py │────▶│  static/data/    │
│  (HTTPS/JupyterHub)│    │  download_remote │     │  *.RDS files     │
│  via REMOTE_RDS_  │     │  _files()        │     │  (local +        │
│   URLS env var   │     │  (RDSDownloader) │     │   downloaded)    │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                                                  ┌────────▼─────────┐
                                                  │  process_file()  │
                                                  │   per file       │
                                                  └────────┬─────────┘
                                                           │
                                                  ┌────────▼─────────┐
                                                  │  checksum check  │
                                                  │  (SHA-256)       │
                                                  └────────┬─────────┘
                                                        │
                                          ┌─────────────▼──────────┐
                                           │  Already processed?    │
                                           │  (file_imports          │
                                           │   table lookup)        │
                                          └──────┬──────────┬──────┘
                                                 │ YES      │ NO
                                                 ▼          ▼
                                            SKIP     ┌─────────────────┐
                                                     │  pyreadr.read_r │
                                                     │  → pandas DF    │
                                                     └────────┬────────┘
                                                              │
                                                     ┌────────▼────────┐
                                                     │  Chunk by       │
                                                     │  chunk_size     │
                                                     │  (default 10k)  │
                                                     └────────┬────────┘
                                                              │
                                                     ┌────────▼────────┐
                                                     │  Map columns    │
                                                     │  XY → coord     │
                                                     │  country        │
                                                     │  province       │
                                                     │  lon, lat       │
                                                     │  Variety        │
                                                     │  Season_type    │
                                                     │  Opt_date       │
                                                     │  Planting_Option│
                                                     └────────┬────────┘
                                                              │
                                                     ┌────────▼────────┐
                                                     │  Batch insert   │
                                                     │  (default 1k)   │
                                                     │  WKT POINT for  │
                                                     │  coordinates    │
                                                     └────────┬────────┘
                                                              │
                                                     ┌────────▼────────┐
                                                      │  Record in       │
                                                      │  file_imports    │
                                                      │  (name + SHA)   │
                                                     └─────────────────┘
```

### Step-by-step

1. **(Optional) Remote download** — `download_remote_files()` (`housekeeping.py:132`) reads `REMOTE_RDS_URLS` from the environment, creates an `RDSDownloader`, and fetches each URL into `static/data/`. Supports bearer tokens, cookies, and custom headers via environment variables. Download failures are logged and skipped without aborting
2. **File discovery** — `load_rds_to_db()` (`housekeeping.py:168`) scans `static/data/` for all `.RDS` files — both pre-existing and freshly downloaded
2. **Concurrent dispatch** — Files are processed in parallel via `ThreadPoolExecutor` (`housekeeping.py:141`)
3. **Checksum calculation** — Each file is hashed with SHA-256 (`app/utils/__init__.py:4`)
4. **Deduplication check** — `FileImportRepo.get_by_checksum()` (`app/repo/file_import.py`) checks the `file_imports` table
5. **RDS parsing** — `pyreadr.read_r()` loads the entire file into a pandas DataFrame (`housekeeping.py:63`)
6. **Chunked processing** — Rows are iterated in chunks of `chunk_size` (default 10,000) to control memory usage
7. **Column mapping** — Each row maps RDS columns to `PlantingRecommendationRecord` fields:
   - `XY` → used as presence check (rows without coordinates are skipped)
   - `country`, `province`, `lon`, `lat`, `Variety`, `Season_type`, `Opt_date`, `Planting_Option` → ORM fields
   - File checksum is attached to every row for traceability
8. **Batch insert** — Accumulated records are bulk-inserted via `PlantingRecommendationRepo.batch_insert()` (`app/repo/planting_recommendation.py`). The `coordinates` geometry is built as `POINT(lon lat)` WKT with SRID 4326
9. **File tracking** — After all rows are inserted, a `FileImport` record (file name + checksum) is saved

### Tables affected

| Table | Action | Key columns |
|---|---|---|
    | `planting_recommendations` | INSERT (bulk) | `check_sum`, `country`, `province`, `coordinates` (POINT), `lon`, `lat`, `variety`, `season_type`, `opt_date`, `planting_option` |
| `file_imports` | INSERT (single) | `check_sum` (unique), `file_name`, `processed_at` |

---

## 2. Serving Flow — API Query

Clients retrieve planting data via `GET /api/v1/planting-data/`, which applies filters, builds a SQLAlchemy query, and returns paginated JSON.

```
┌──────────┐     ┌──────────────────┐     ┌──────────────────────┐
│  Client   │────▶│  flask-openapi3  │────▶│  PlantingDataFilter  │
│  HTTP GET │     │  APIBlueprint     │     │  (Pydantic validation)│
└──────────┘     └──────────────────┘     └──────────┬───────────┘
                                                      │
                                             ┌────────▼───────────┐
                                              │  PlantingRecommendationRepo.│
                                              │  get_paginated_data         │
                                             └────────┬───────────┘
                                                      │
                                             ┌────────▼───────────┐
                                             │  get_filtered_data │
                                             │  builds Query      │
                                             └────────┬───────────┘
                                                      │
                    ┌──────────────────────────────────┼──────────────────────────────┐
                    ▼                                  ▼                              ▼
          ┌─────────────────┐                ┌─────────────────┐          ┌─────────────────────┐
          │  Spatial filter  │                │  Field filters   │          │  Pagination          │
          │  ST_DWithin      │                │  country         │          │  query.paginate()    │
          │  (coordinates +  │                │  province (ILIKE)│          │  page, per_page      │
          │   radius meters) │                │  variety         │          └──────────┬──────────┘
          └─────────────────┘                │  season_type     │                     │
                                              │  opt_date        │                     │
                                              │  planting_option │                     │
                                              └─────────────────┘                     │
                                                                                      ▼
                                                                             ┌──────────────────┐
                                                                             │  JSON response   │
                                                                             │  data[]           │
                                                                             │  total            │
                                                                             │  pages            │
                                                                             │  current_page     │
                                                                             │  per_page         │
                                                                             └──────────────────┘
```

### Step-by-step

1. **HTTP request** — `GET /api/v1/planting-data/?country=Zambia&variety=Soybean&page=1&per_page=20` (`app/api/planting_data.py:29`)
2. **Parameter extraction** — `page` and `per_page` from `request.args`; all filter params are injected as a `PlantingDataFilter` Pydantic model (`app/dto/data_filters.py:19`)
3. **Validation** — Pydantic validators check:
   - `coordinates`: must match `lon,lat` format; lat in [-90, 90], lon in [-180, 180]
   - `opt_date`: must be `YYYY-MM-DD`
   - Whitespace is stripped; enum values resolved
4. **Query building** — `PlantingRecommendationRepo.get_filtered_data()` (`app/repo/planting_recommendation.py`) constructs a SQLAlchemy query with optional filters:
   - **Spatial**: If `coordinates` + `radius` provided, uses `ST_DWithin(geometry, point, radius)` for PostGIS radius search
   - **Exact match**: `country`, `variety`, `season_type`, `opt_date`, `planting_option`
   - **Partial/ILIKE**: `province` uses `ILIKE '%search%'`
5. **Pagination** — `query.paginate(page, per_page)` returns a `QueryPagination` object with items, total count, and page metadata (`app/repo/planting_recommendation.py`)
6. **Response mapping** — Each ORM `PlantingRecommendation` row is converted to a `PlantingRecommendationRecord` dict (`app/api/planting_data.py`)
7. **JSON response** — Returns `{ data: [...], total, pages, current_page, per_page }` with HTTP 200, or 500 on error

### Response shape

```json
{
  "data": [
    {
      "id": 1,
      "country": "Zambia",
      "province": "Southern",
      "lat": -17.85,
      "lon": 25.92,
      "variety": "Soybean",
      "season_type": "Main",
      "opt_date": "2024-11-15",
      "planting_option": 1,
      "check_sum": "abc123..."
    }
  ],
  "total": 42,
  "pages": 5,
  "current_page": 1,
  "per_page": 10
}
```

---

## 3. Database Schema

### `planting_recommendations`

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT PK | Auto-increment ID |
| `check_sum` | VARCHAR(100) | SHA-256 of source file |
| `country` | VARCHAR(20) | Country name |
| `province` | VARCHAR(20) | Province/region name |
| `coordinates` | GEOMETRY(POINT, 4326) | Spatial point (PostGIS) |
| `lon` | FLOAT | Longitude (denormalized) |
| `lat` | FLOAT | Latitude (denormalized) |
| `variety` | VARCHAR(20) | Crop variety |
| `season_type` | VARCHAR(20) | Season classification |
| `opt_date` | VARCHAR(8) | Optimal sowing date |
| `planting_option` | INTEGER | Planting option ID |
| `created_at` | DATETIME | Auto-set on insert |
| `updated_at` | DATETIME | Auto-set on update |

Indexes: `check_sum`, `coordinates` (GiST), `country`, `province`, `lon`, `lat`, `variety`, `season_type`, `opt_date`, `planting_option`.

### `file_imports`

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT PK | Auto-increment ID |
| `check_sum` | VARCHAR(100) UNIQUE | SHA-256 of processed file |
| `file_name` | VARCHAR(120) | Original file name |
| `processed_at` | DATETIME | Auto-set on insert |

---

## 4. Key Modules Reference

| Layer | Module | Responsibility |
|---|---|---|
| ETL | `housekeeping.py` | Remote download, RDS file discovery, parallel dispatch, chunked processing |
| Download | `app/utils/downloader.py` | `RDSDownloader` — remote file download with auth support (used by housekeeping) |
| Checksum | `app/utils/__init__.py` | `calculate_file_checksum()` — file hashing |
| Parsing | `pyreadr` (external) | RDS → pandas DataFrame conversion |
| Models | `app/models/kvuno.py` | `PlantingRecommendation`, `FileImport`, `ImportConflict` ORM models |
| DB Conn | `app/models/database_conn.py` | `MyDb` singleton — SQLAlchemy initialization |
| Repo | `app/repo/planting_recommendation.py` | `PlantingRecommendationRepo` — CRUD, batch insert, filtered queries |
| Repo | `app/repo/file_import.py` | `FileImportRepo` — deduplication checks |
| DTO | `app/dto/data_filters.py` | `PlantingDataFilter` — Pydantic query validation |
| DTO | `app/dto/planting_recommendation.py` | Response models for OpenAPI schema |
| API | `app/api/planting_data.py` | `GET /api/v1/planting-data/` endpoint |
| Routes | `app/routes/main.py` | `/` redirect, `/health` check |
| App | `app/__init__.py` | `create_app()` — Flask factory, CORS, DB init |
| Config | `app/config.py` | App name, version, API prefix constants |
