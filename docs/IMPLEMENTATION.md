# Implementation Roadmap — Housekeeping Robustness

Checklist of improvements to harden `housekeeping.py` against failures, improve performance, and add operational visibility.

---

## High Priority

- [x] **Batch-level savepoints** — Each batch insert is wrapped in `session.begin_nested()` (nested transaction). Failed batches are skipped and counted; the file is still recorded in `processed_files` with a warning.

- [x] **Retry with exponential backoff** — Added `retry_db()` helper (3 attempts, 1s/2s/4s backoff). Wraps checksum lookup and each savepoint batch insert.

- [x] **Replace `iterrows` with vectorized batch building** — Replaced the `iterrows()` loop with `chunk.dropna(subset=['XY']).replace({pd.NA: None}).to_dict('records')` for ~100x speedup.

- [x] **Graceful shutdown** — Signal handlers set a `shutdown_requested` flag checked at each batch boundary. On first signal: completes current batch, commits, and exits (does NOT mark file as processed). On second signal: raises `KeyboardInterrupt`/`SystemExit` for force-quit. SIGTERM protected against Windows `AttributeError`.

---

## Medium Priority

- [ ] **Per-file error aggregation in concurrent executor** — Replace `executor.map()` with `concurrent.futures.as_completed()` so per-file exceptions are collected and summarized, rather than silently swallowed. Log a final summary of succeeded/failed files.

- [ ] **Resumable processing (offset tracking)** — Add an `offset` column to `processed_files` (or a new `processing_state` table) to track the last committed row per file. On restart, skip already-inserted rows instead of re-processing from the beginning.

- [ ] **Pre-flight DB health check** — At the start of `load_rds_to_db()`, run a `SELECT 1` to confirm the database is reachable before spending time downloading or processing files.

- [ ] **Configurable column mapping** — Accept a column-name mapping (via env var `RDS_COLUMN_MAP` as JSON, e.g. `{"XY": "coordinates", "Variety": "variety"}`) so the script adapts to different RDS schemas without hardcoded column names.

---

## Low Priority

- [ ] **Streaming RDS reader** — Investigate whether `pyreadr` supports chunked reads or evaluate alternative RDS parsers that stream rows instead of loading the full dataset into memory.

- [ ] **File watcher mode** — Add a `--watch` flag that monitors `static/data/` for new `.RDS` files and processes them on arrival, keeping the database in sync without manual re-runs.

- [ ] **Telemetry / progress tracking** — Emit structured JSON log lines at each phase (download start/end, batch committed, file complete) for ingestion into a monitoring pipeline.

- [ ] **Dry-run mode** — Add a `--dry-run` flag that scans and reports what would be processed (new files, already-processed files, row counts) without touching the database.
