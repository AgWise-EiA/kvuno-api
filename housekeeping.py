"""
Housekeeping script that processes RDS files and inserts data into the database
"""
import concurrent.futures
import json
import os
import signal
import time

import pandas as pd
import pyreadr
from dotenv import load_dotenv
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

# Load environment variables from .env file
load_dotenv()

loglevel = os.getenv('LOG_LEVEL', 'INFO').lower()
shared_logger = SharedLogger(level=loglevel)
logger = shared_logger.get_logger()

app = create_app()

processed_files_repo = ProcessedFilesRepo()
crop_data_repo = CropDataRepo()

# Graceful shutdown flag
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


# Register signal handlers (SIGTERM not available on Windows)
try:
    signal.signal(signal.SIGTERM, _handle_sigterm)
except (ValueError, AttributeError):
    pass
signal.signal(signal.SIGINT, _handle_sigint)


def load_column_map() -> dict[str, str]:
    """Load column name mapping from RDS_COLUMN_MAP env var (JSON), falling back to defaults.

    Returns a dict of ``{rds_column_name: crop_data_record_attr}``.
    """
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


def process_file(file_path: str, batch_size: int = 1000, chunk_size: int = 10000):
    """
    Processes a single file by reading its contents in chunks, converting data to `PlantingDataREcord` instances,
    and inserting records into the database. The file is only processed if its checksum is not
    already recorded in the processed_files repository.

    Args:
        file_path (str): The path to the file to be processed.
        batch_size (int): The number of records to batch insert into the database. Defaults to 1000.
        chunk_size (int): The number of rows to read at a time from the RDS file. Defaults to 10000.

    Raises:
        FileNotFoundError: If the specified file is not found.
    """

    start_time = time.time()  # Start timing
    file_name = os.path.basename(file_path)  # Extract the filename without path

    column_map = load_column_map()

    with app.app_context():
        checksum = None
        try:
            checksum = calculate_file_checksum(file_path, logger)

            if retry_db(lambda: processed_files_repo.get_processed_file_by_checksum(checksum)):
                logger.warning(f"File {file_name} is already processed. Checksum: {checksum}")
                return  # Skip processing if file is already processed

            logger.info(f"Processing file {file_name} in chunks of size {chunk_size}")

            result = pyreadr.read_r(file_path)
            data = result[None]  # Assuming this returns a DataFrame or equivalent
            num_rows = len(data)

            session = MyDb.get_db().session
            failed_batches = 0
            completed_batches = 0

            # Outer transaction — explicit begin/commit so we can commit on interrupt
            session.begin()
            try:
                for start in range(0, num_rows, chunk_size):
                    if shutdown_requested:
                        logger.warning("Shutdown requested — breaking after current chunk")
                        break

                    end = min(start + chunk_size, num_rows)
                    chunk = data.iloc[start:end]

                    logger.debug(f"Processing chunk from rows {start} to {end} of {file_name}")

                    filtered = chunk.dropna(subset=['XY'])
                    skipped = len(chunk) - len(filtered)
                    if skipped:
                        logger.warning(f"Skipped {skipped} row(s) in chunk {start}-{end} due to empty coordinates")

                    if filtered.empty:
                        continue

                    records_data = filtered.replace({pd.NA: None, pd.NaT: None}).to_dict('records')

                    # Build this batch from chunk records using configurable column map
                    batch = []
                    for rd in records_data:
                        kwargs = {'id': None, 'check_sum': checksum}
                        for rds_col, target_attr in column_map.items():
                            value = rd.get(rds_col)
                            if target_attr == 'planting_option' and value is not None:
                                value = int(value)
                            kwargs[target_attr] = value
                        batch.append(CropDataRecord(**kwargs))

                    # Flush batches with savepoints — each batch is a nested transaction
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
                        except SQLAlchemyError:
                            failed_batches += 1
                            logger.error(f"Batch {i // batch_size + 1} failed in {file_name}, skipping")

                    if shutdown_requested:
                        break

                # On graceful shutdown, commit completed batches but don't mark file as processed
                # so next run can resume or re-process from scratch
                if not shutdown_requested:
                    session.add(ProcessedFiles(file_name=file_name, check_sum=checksum))
            except BaseException:
                session.rollback()
                raise

            session.commit()

            if shutdown_requested:
                logger.warning(
                    f"Graceful shutdown — committed {completed_batches} batches from {file_name}, "
                    f"did NOT mark file as processed"
                )

            if failed_batches:
                logger.warning(f"File {file_name} processed with {failed_batches} failed batch(es)")
            else:
                logger.info(f"File {file_name} processed and recorded")

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


def download_remote_files(data_folder: str) -> list[str]:
    """
    Downloads remote RDS files defined in the REMOTE_RDS_URLS environment variable.

    URLs should be semicolon-delimited. Optional auth can be configured via:
      - REMOTE_RDS_TOKEN: Bearer token
      - REMOTE_RDS_COOKIES: Comma-separated key=value pairs
      - REMOTE_RDS_HEADERS: Comma-separated key:value pairs

    Download errors are logged and skipped gracefully.

    Args:
        data_folder (str): Directory to save downloaded files into.

    Returns:
        list[str]: Paths of successfully downloaded files.
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
    for url in urls:
        try:
            path = downloader.download(url)
            downloaded.append(path)
        except Exception as e:
            logger.warning(f"Skipping failed download {url}: {e}")

    logger.info(f"Downloaded {len(downloaded)}/{len(urls)} remote file(s)")
    return downloaded


def db_health_check():
    """Run a quick query to confirm the database is reachable. Raises on failure."""
    with app.app_context():
        session = MyDb.get_db().session
        session.execute(db_text("SELECT 1"))
        logger.info("Database health check passed")


def load_rds_to_db(data_folder: str, batch_size: int = 1000, chunk_size: int = 10000):
    """
    Loads and processes all RDS files from a specified directory by submitting them for processing
    using a thread pool executor. Each file is processed in a separate thread.

    Remote RDS files defined in the REMOTE_RDS_URLS env var are downloaded first.

    Args:
        data_folder (str): The directory containing the RDS files to be processed.
        batch_size (int): The number of records to batch insert into the database. Defaults to 1000.
        chunk_size (int): The number of rows to read at a time from each RDS file. Defaults to 10000.
    """
    os.makedirs(data_folder, exist_ok=True)
    global_start_time = time.time()

    db_health_check()

    download_remote_files(data_folder)

    file_paths = [os.path.join(data_folder, f) for f in os.listdir(data_folder) if f.endswith('.RDS')]

    logger.info(f"Starting to process {len(file_paths)} file(s) from {data_folder}")

    with app.app_context():
        failed_files = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(process_file, fp, batch_size, chunk_size): fp
                for fp in file_paths
            }
            for future in concurrent.futures.as_completed(futures):
                fp = futures[future]
                try:
                    future.result()
                    logger.info(f"Completed processing {os.path.basename(fp)}")
                except Exception as e:
                    failed_files.append((fp, e))
                    logger.error(f"Failed to process {os.path.basename(fp)}: {e}")

        if failed_files:
            logger.error(
                f"Processed {len(file_paths) - len(failed_files)}/{len(file_paths)} file(s), "
                f"{len(failed_files)} failed"
            )
            for fp, exc in failed_files:
                logger.error(f"  {os.path.basename(fp)}: {exc}")

    global_elapsed_time = time.time() - global_start_time
    if global_elapsed_time > 60:
        minutes, seconds = divmod(global_elapsed_time, 60)
        logger.info(f"Processing all files took {int(minutes)} minutes and {seconds:.2f} seconds")
    else:
        logger.info(f"Processing all files took {global_elapsed_time:.2f} seconds")


if __name__ == '__main__':
    rds_folder = os.path.join("static/", 'data')
    load_rds_to_db(data_folder=rds_folder, batch_size=2000, chunk_size=10000)
