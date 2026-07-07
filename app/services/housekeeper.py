"""
Housekeeping — RDS/Parquet file ingestion service.

Used as the primary processing module by both the Flask app (upload API,
startup background job) and the standalone CLI (``python housekeeping.py``).
"""
import concurrent.futures
import json
import os
import signal
import threading
import time

import pandas as pd
import pyreadr
from dotenv import load_dotenv
from flask import current_app
from geoalchemy2 import WKTElement
from sqlalchemy import text as db_text
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.dto.crop_data_resp import CropDataRecord
from app.models.database_conn import MyDb
from app.models.kvuno import CropData, ProcessedFiles
from app.repo.crop_data import CropDataRepo
from app.repo.processed_files import ProcessedFilesRepo
from app.utils import calculate_file_checksum
from app.utils.downloader import RDSDownloader
from app.utils.logging import SharedLogger

load_dotenv()

loglevel = os.getenv('LOG_LEVEL', 'INFO').upper()
shared_logger = SharedLogger(level=loglevel)
logger = shared_logger.get_logger()

_app = None
_BACKGROUND_THREADS: list[threading.Thread] = []
DATA_DIR = os.getenv('HOUSEKEEPING_DATA_DIR', os.path.join("static", "data"))


# ── App management ─────────────────────────────────────────────

def _get_app():
    global _app
    if _app is None:
        _app = create_app()
    return _app


def set_app(app_instance):
    """Override the module-level app (used when integrating into the Flask server)."""
    global _app
    _app = app_instance


# ── Settings ───────────────────────────────────────────────────

def housekeeping_settings() -> dict:
    """Read housekeeping parameters from environment variables.

    Returns a dict suitable for passing as ``**kwargs`` to
    :func:`load_rds_to_db` or :func:`process_file`.
    """
    return {
        'batch_size': int(os.getenv('HOUSEKEEPING_BATCH_SIZE', '2000')),
        'chunk_size': int(os.getenv('HOUSEKEEPING_CHUNK_SIZE', '10000')),
        'checkpoint_interval': int(os.getenv('HOUSEKEEPING_CHECKPOINT_INTERVAL', '50')),
    }


# ── Repos ──────────────────────────────────────────────────────

processed_files_repo = ProcessedFilesRepo()
crop_data_repo = CropDataRepo()


# ── Graceful shutdown ──────────────────────────────────────────

shutdown_requested = False


def _handle_sigterm(signum, frame):
    global shutdown_requested
    if shutdown_requested:
        raise SystemExit(1)
    shutdown_requested = True
    logger.warning("SIGTERM received — shutting down after current batch")


def _handle_sigint(signum, frame):
    global shutdown_requested
    if shutdown_requested:
        raise KeyboardInterrupt()
    shutdown_requested = True
    logger.warning("KeyboardInterrupt received — shutting down after current batch")


try:
    signal.signal(signal.SIGTERM, _handle_sigterm)
except (ValueError, AttributeError):
    pass
signal.signal(signal.SIGINT, _handle_sigint)


# ── Telemetry ──────────────────────────────────────────────────

def emit_event(event: str, **kwargs):
    """Write a structured JSON event line to stderr for monitoring ingestion."""
    record = {"event": event, "timestamp": time.time()}
    record.update(kwargs)
    print(json.dumps(record), file=__import__('sys').stderr, flush=True)


# ── Column mapping ─────────────────────────────────────────────

def load_column_map() -> dict[str, str]:
    """Load column name mapping from RDS_COLUMN_MAP env var (JSON), falling back to defaults."""
    default_map = {
        'country': 'country',
        'province': 'province',
        'lon': 'lon',
        'lat': 'lat',
        'Variety': 'variety',
        'Season_type': 'season_type',
        'Opt_date': 'opt_date',
        'Planting_Option': 'planting_option',
    }
    raw = os.getenv('RDS_COLUMN_MAP')
    if raw:
        try:
            overrides = json.loads(raw)
            default_map.update(overrides)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Invalid RDS_COLUMN_MAP JSON, using defaults: {e}")
    return default_map


# ── DB helpers ─────────────────────────────────────────────────

def retry_db(fn, attempts: int = 3, base_delay: float = 1.0):
    """Call *fn* with retries on SQLAlchemyError using exponential backoff."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except SQLAlchemyError as e:
            last_exc = e
            if attempt < attempts:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"DB error (attempt {attempt}/{attempts}): {e}. Retrying in {delay}s")
                time.sleep(delay)
    logger.error(f"DB operation failed after {attempts} attempts: {last_exc}")
    raise last_exc


def db_health_check():
    """Run a quick query to confirm the database is reachable. Raises on failure."""
    with _get_app().app_context():
        session = MyDb.get_db().session
        session.execute(db_text("SELECT 1"))
        logger.info("Database health check passed")


# ── Remote download ────────────────────────────────────────────

def download_remote_files(data_folder: str) -> list[str]:
    """
    Downloads remote RDS files defined in the REMOTE_RDS_URLS environment variable.

    URLs should be semicolon-delimited. Optional auth can be configured via:
      - REMOTE_RDS_TOKEN: Bearer token
      - REMOTE_RDS_COOKIES: Comma-separated key=value pairs
      - REMOTE_RDS_HEADERS: Comma-separated key:value pairs

    Download errors are logged and skipped gracefully.
    """
    urls_raw = os.getenv("REMOTE_RDS_URLS", "").strip()
    if not urls_raw:
        logger.info("No REMOTE_RDS_URLS defined, skipping remote download")
        return []

    urls = [u.strip() for u in urls_raw.split(";") if u.strip()]
    logger.info(f"Found {len(urls)} remote RDS URL(s) to download")

    token = os.getenv("REMOTE_RDS_TOKEN")
    cookies_raw = os.getenv("REMOTE_RDS_COOKIES")
    headers_raw = os.getenv("REMOTE_RDS_HEADERS")

    cookies = {}
    if cookies_raw:
        for pair in cookies_raw.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                cookies[k.strip()] = v.strip()

    headers = {}
    if headers_raw:
        for pair in headers_raw.split(","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                headers[k.strip()] = v.strip()

    downloader = RDSDownloader(data_dir=data_folder, logger=logger)
    if token:
        downloader.set_bearer_token(token)
    if cookies:
        downloader.set_cookies(cookies)
    if headers:
        downloader.set_headers(headers)

    downloaded = []
    emit_event("file.download_start", url_count=len(urls))
    for url in urls:
        try:
            path = downloader.download(url)
            downloaded.append(path)
        except Exception as e:
            logger.warning(f"Skipping failed download {url}: {e}")

    emit_event("file.download_end", downloaded=len(downloaded), total=len(urls))
    logger.info(f"Downloaded {len(downloaded)}/{len(urls)} remote file(s)")
    return downloaded


# ── File processing ────────────────────────────────────────────

def process_file(
    file_path: str,
    batch_size: int = 1000,
    chunk_size: int = 10000,
    checkpoint_interval: int = 50,
    dry_run: bool = False,
):
    """
    Processes a single file by reading its contents in chunks, converting data to
    :class:`PlantingDataRecord` instances, and inserting records into the database.
    Supports resumable processing via checkpoint-based commits.

    Accepts both ``.RDS`` (via pyreadr) and ``.parquet`` files.
    """
    start_time = time.time()
    file_name = os.path.basename(file_path)

    column_map = load_column_map()

    with _get_app().app_context():
        checksum = None
        try:
            checksum = calculate_file_checksum(file_path, logger)

            if dry_run:
                existing = processed_files_repo.get_processed_file_by_checksum(checksum)
                if existing and existing.offset is None:
                    logger.info(f"[DRY RUN] {file_name} — already processed, would skip")
                elif existing and existing.offset is not None:
                    logger.info(f"[DRY RUN] {file_name} — partially processed at offset {existing.offset}, would resume")
                else:
                    logger.info(f"[DRY RUN] {file_name} — would process {os.path.getsize(file_path)} bytes")
                return

            existing = retry_db(lambda: processed_files_repo.get_processed_file_by_checksum(checksum))
            resume_offset = 0
            if existing and existing.offset is None:
                logger.warning(f"File {file_name} is already fully processed. Checksum: {checksum}")
                return
            if existing and existing.offset is not None:
                resume_offset = existing.offset
                logger.info(f"Resuming {file_name} from row {resume_offset} (checksum: {checksum})")

            if file_path.endswith('.parquet'):
                data = pd.read_parquet(file_path)
            else:
                result = pyreadr.read_r(file_path)
                data = result[None]
            num_rows = len(data)

            if resume_offset >= num_rows:
                logger.warning(f"File {file_name} offset ({resume_offset}) >= total rows ({num_rows}), skipping")
                return

            emit_event("file.processing_start", file=file_name, checksum=checksum,
                       total_rows=num_rows, resume_offset=resume_offset)
            logger.info(f"Processing file {file_name} in chunks of size {chunk_size}")

            session = MyDb.get_db().session
            failed_batches = 0
            completed_batches = 0
            batches_since_checkpoint = 0
            last_committed_row = resume_offset

            try:
                for chunk_start in range(resume_offset, num_rows, chunk_size):
                    if shutdown_requested:
                        logger.warning("Shutdown requested — breaking after current chunk")
                        break

                    chunk_end = min(chunk_start + chunk_size, num_rows)
                    chunk = data.iloc[chunk_start:chunk_end]

                    logger.debug(f"Processing chunk from rows {chunk_start} to {chunk_end} of {file_name}")

                    filtered = chunk.dropna(subset=['XY'])
                    skipped = len(chunk) - len(filtered)
                    if skipped:
                        logger.warning(f"Skipped {skipped} row(s) in chunk {chunk_start}-{chunk_end} due to empty coordinates")

                    if filtered.empty:
                        continue

                    records_data = filtered.replace({pd.NA: None, pd.NaT: None}).to_dict('records')

                    batch = []
                    for rd in records_data:
                        kwargs = {'id': None, 'check_sum': checksum}
                        for rds_col, target_attr in column_map.items():
                            value = rd.get(rds_col)
                            if target_attr == 'planting_option' and value is not None:
                                value = int(value)
                            kwargs[target_attr] = value
                        batch.append(CropDataRecord(**kwargs))

                    for i in range(0, len(batch), batch_size):
                        if shutdown_requested:
                            logger.warning("Shutdown requested — breaking after current batch")
                            break

                        sub = batch[i:i + batch_size]
                        try:
                            def _flush_batch(rows):
                                with session.begin_nested():
                                    mappings = [
                                        {
                                            **r.__dict__,
                                            'coordinates': WKTElement(f"POINT({r.lon} {r.lat})", srid=4326)
                                            if r.lat and r.lon
                                            else None
                                        }
                                        for r in rows
                                    ]
                                    session.bulk_insert_mappings(CropData, mappings)
                            retry_db(lambda: _flush_batch(sub), attempts=2)
                            completed_batches += 1
                            batches_since_checkpoint += 1
                        except SQLAlchemyError:
                            failed_batches += 1
                            logger.error(f"Batch {i // batch_size + 1} failed in {file_name}, skipping")

                    if not shutdown_requested:
                        last_committed_row = chunk_end

                    if batches_since_checkpoint >= checkpoint_interval and not shutdown_requested:
                        session.commit()
                        processed_files_repo.upsert_offset(checksum, file_name, chunk_end)
                        batches_since_checkpoint = 0
                        logger.debug(f"Checkpoint committed at row {chunk_end}")

                    if shutdown_requested:
                        break

            except BaseException:
                session.rollback()
                raise

            session.commit()

            elapsed = time.time() - start_time
            emit_event("file.processing_end", file=file_name, checksum=checksum,
                       elapsed=round(elapsed, 2), completed_batches=completed_batches,
                       failed_batches=failed_batches, shutdown=shutdown_requested)

            if shutdown_requested:
                processed_files_repo.upsert_offset(checksum, file_name, last_committed_row)
                logger.warning(
                    f"Graceful shutdown — committed {completed_batches} batches from {file_name}, "
                    f"offset {last_committed_row} persisted"
                )
            else:
                processed_files_repo.upsert_offset(checksum, file_name, num_rows)
                logger.info(f"File {file_name} fully processed and recorded")

            if failed_batches:
                logger.warning(f"File {file_name} processed with {failed_batches} failed batch(es)")

        except FileNotFoundError as e:
            logger.error(f"Failed to process file {file_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing file {file_name}: {e}")
        finally:
            elapsed_time = time.time() - start_time
            if elapsed_time > 60:
                minutes, seconds = divmod(elapsed_time, 60)
                logger.info(f"Processing file {file_name} took {int(minutes)} minutes and {seconds:.2f} seconds")
            else:
                logger.info(f"Processing file {file_name} took {elapsed_time:.2f} seconds")


# ── Batch processing ───────────────────────────────────────────

def load_rds_to_db(data_folder: str, batch_size: int = 1000, chunk_size: int = 10000,
                   checkpoint_interval: int = 50, dry_run: bool = False):
    """
    Loads and processes all RDS/Parquet files from *data_folder* using a thread pool.

    Remote RDS files defined in the ``REMOTE_RDS_URLS`` env var are downloaded first.
    """
    os.makedirs(data_folder, exist_ok=True)
    global_start_time = time.time()

    db_health_check()
    download_remote_files(data_folder)

    file_paths = [
        os.path.join(data_folder, f)
        for f in os.listdir(data_folder)
        if f.endswith('.RDS') or f.endswith('.parquet')
    ]

    logger.info(f"Starting to process {len(file_paths)} file(s) from {data_folder}")
    emit_event("housekeeping.start", file_count=len(file_paths), data_folder=data_folder)

    failed_count = 0
    with _get_app().app_context():
        failed_files = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(process_file, fp, batch_size, chunk_size, checkpoint_interval, dry_run): fp
                for fp in file_paths
            }
            for future in concurrent.futures.as_completed(futures):
                fp = futures[future]
                try:
                    future.result()
                    logger.info(f"Completed processing {os.path.basename(fp)}")
                except Exception as e:
                    failed_files.append((fp, e))
                    failed_count += 1
                    logger.error(f"Failed to process {os.path.basename(fp)}: {e}")

        if failed_files:
            logger.error(
                f"Processed {len(file_paths) - len(failed_files)}/{len(file_paths)} file(s), "
                f"{len(failed_files)} failed"
            )
            for fp, exc in failed_files:
                logger.error(f"  {os.path.basename(fp)}: {exc}")

    global_elapsed_time = time.time() - global_start_time
    emit_event("housekeeping.end", elapsed=round(global_elapsed_time, 2), failed=failed_count)
    if global_elapsed_time > 60:
        minutes, seconds = divmod(global_elapsed_time, 60)
        logger.info(f"Processing all files took {int(minutes)} minutes and {seconds:.2f} seconds")
    else:
        logger.info(f"Processing all files took {global_elapsed_time:.2f} seconds")


# ── File watcher ───────────────────────────────────────────────

def watch_directory(
    data_folder: str,
    batch_size: int = 1000,
    chunk_size: int = 10000,
    checkpoint_interval: int = 50,
    dry_run: bool = False,
):
    """Watch *data_folder* for new files and process them as they arrive.

    Requires ``watchdog`` (install with ``pip install kvuno-api[watch]``).
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        logger.error(
            "watchdog is required for --watch mode. Install it with: "
            "pip install kvuno-api[watch]  or  poetry install --extras watch"
        )
        raise

    os.makedirs(data_folder, exist_ok=True)

    class RDSHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            if not (event.src_path.endswith('.RDS') or event.src_path.endswith('.parquet')):
                return
            logger.info(f"New file detected: {event.src_path}")
            process_file(event.src_path, batch_size=batch_size, chunk_size=chunk_size,
                         checkpoint_interval=checkpoint_interval, dry_run=dry_run)

    event_handler = RDSHandler()
    observer = Observer()
    observer.schedule(event_handler, data_folder, recursive=False)
    observer.start()
    logger.info(f"Watching {data_folder} for new files...")

    try:
        while True:
            time.sleep(1)
            if shutdown_requested:
                logger.warning("Shutdown requested — stopping file watcher")
                break
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


# ── Async wrappers (Flask integration) ─────────────────────────

def process_file_async(file_path: str, app=None):
    """Process a single file in a background thread (non-blocking).

    Used by the upload API endpoint.
    """
    app = app or current_app._get_current_object()
    def _run():
        with app.app_context():
            set_app(app)
            process_file(file_path=file_path, **housekeeping_settings())
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    _BACKGROUND_THREADS.append(thread)
    return thread


_STARTUP_LOCK_ID = 42_042_042_042  # arbitrary bigint for pg_try_advisory_lock


def process_pending(app=None):
    """Start background processing of unprocessed files (non-blocking).

    Uses a Postgres session-level advisory lock on a dedicated connection
    so that only the first worker instance runs startup processing —
    subsequent instances silently skip. The lock is held on a persistent
    connection for the entire duration and auto-released when the thread
    finishes (connection is garbage-collected).

    Called once at Flask app startup.
    """
    app = app or current_app._get_current_object()
    def _run():
        with app.app_context():
            set_app(app)
            lock_conn = MyDb.get_db().engine.connect().execution_options(isolation_level="AUTOCOMMIT")
            locked = lock_conn.execute(
                db_text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": _STARTUP_LOCK_ID},
            ).scalar()
            if not locked:
                lock_conn.close()
                logger.info("Startup processing skipped — another instance holds the lock")
                return

            # Lock acquired — hold lock_conn open for the entire run
            load_rds_to_db(data_folder=DATA_DIR, **housekeeping_settings())
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    _BACKGROUND_THREADS.append(thread)
    return thread


# ── CLI dispatcher ─────────────────────────────────────────────

def cli_run(args):
    """Entry point for the ``python housekeeping.py`` CLI.

    Merges CLI args (which take precedence) over env-var sourced defaults.
    """
    settings = housekeeping_settings()
    for key in ('batch_size', 'chunk_size', 'checkpoint_interval'):
        cli_val = getattr(args, key, None)
        if cli_val is not None:
            settings[key] = cli_val

    data_folder = args.data_folder
    os.makedirs(data_folder, exist_ok=True)
    set_app(_get_app())

    if args.watch:
        watch_directory(data_folder, dry_run=args.dry_run, **settings)
    else:
        with _get_app().app_context():
            load_rds_to_db(data_folder=data_folder, dry_run=args.dry_run, **settings)
