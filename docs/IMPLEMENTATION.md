# Implementation Roadmap — Housekeeping Robustness

Checklist of improvements to harden `housekeeping.py` against failures, improve performance, and add operational visibility.

---

## High Priority

- [ ] **Batch-level savepoints** — Wrap each DB batch insert in a SQLAlchemy savepoint (nested transaction) so partial commits are rolled back if a batch fails mid-file. The file is only recorded in `processed_files` after all batches succeed.

- [ ] **Retry with exponential backoff** — Wrap DB operations (batch insert, checksum lookup) with a retry decorator (3 attempts, 1s/2s/4s backoff) to handle transient connection drops or deadlocks.

- [ ] **Replace `iterrows` with vectorized batch building** — The current `for index, row in chunk.iterrows()` loop is ~100x slower than building batches with pandas vectorized operations. Use `df.to_dict('records')` with a column transform step instead.

- [ ] **Graceful shutdown** — Catch `KeyboardInterrupt` and `SIGTERM` in `process_file()` to flush the current in-progress batch before exiting, preventing data loss during manual interruption.

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
