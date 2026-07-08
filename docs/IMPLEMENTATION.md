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

- [x] **Per-file error aggregation in concurrent executor** — Replaced `executor.map()` (aborts all on first failure) with `executor.submit()` + `as_completed()`. Each future is individually caught; per-file errors are logged and aggregated for final summary.

- [x] **Resumable processing (offset tracking)** — Added `offset` column to `processed_files` table + repo method `upsert_offset()`. `process_file()` checkpoints every `checkpoint_interval` batches (default 50), committing the outer transaction and persisting offset via a separate session. On restart, skips rows before the stored offset. Graceful shutdown persists the last committed row offset so the next run resumes from there.

- [x] **Pre-flight DB health check** — `db_health_check()` runs `SELECT 1` at the start of `load_rds_to_db()` before downloading or processing any files. Raises immediately if the database is unreachable.

- [x] **Configurable column mapping** — Added `load_column_map()` reading `RDS_COLUMN_MAP` env var (JSON). Defaults match the original hardcoded mapping. Record builder uses the map instead of hardcoded `.get()` calls.

---

## Low Priority

- [x] **Streaming RDS reader (research)** — Investigated: RDS is a serialized R object format; both `pyreadr` and `rds2py` deserialize in one pass. No streaming parser exists. Added `rds_to_parquet.py` utility to convert RDS → Parquet (splittable, columnar) for large files. Update `housekeeping.py` to prefer `.parquet` when available.

- [x] **File watcher mode** — Added `--watch` CLI flag using `watchdog`. Monitors the data directory for new `.RDS`/`.parquet` files and processes them on arrival. Install with `pip install kvuno-api[watch]`.

- [x] **Telemetry / progress tracking** — Added `emit_event()` helper writing structured JSON lines to stderr. Fires at: `housekeeping.start/end`, `file.download_start/end`, `file.processing_start/end`.

- [x] **Dry-run mode** — Added `--dry-run` CLI flag. Each file reports its status (already processed, partially processed with offset, or new) and exits without modifying the database.
