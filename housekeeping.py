"""
Housekeeping script that processes RDS files and inserts data into the database
"""
import concurrent.futures
import logging
import os
import time

import pandas as pd
import pyreadr
from dotenv import load_dotenv

from app import create_app
from app.dto.crop_data_resp import CropDataRecord
from app.models.kvuno import ProcessedFiles
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

    with app.app_context():
        try:
            checksum = calculate_file_checksum(file_path, logger)

            if processed_files_repo.get_processed_file_by_checksum(checksum):
                logger.warning(f"File {file_name} is already processed. Checksum: {checksum}")
                return  # Skip processing if file is already processed

            logger.info(f"Processing file {file_name} in chunks of size {chunk_size}")

            # Initialize batch processing
            crop_data_records = []

            result = pyreadr.read_r(file_path)
            data = result[None]  # Assuming this returns a DataFrame or equivalent
            num_rows = len(data)

            # Process the file in chunks
            for start in range(0, num_rows, chunk_size):
                end = min(start + chunk_size, num_rows)
                chunk = data.iloc[start:end]

                logger.debug(f"Processing chunk from rows {start} to {end} of {file_name}")

                for index, row in chunk.iterrows():
                    logger.debug(f"Processing row {index} from {file_name}")
                    coordinates = row['XY'] if pd.notna(row['XY']) else None
                    if coordinates:
                        record = CropDataRecord(
                            id=None,
                            country=row['country'] if pd.notna(row['country']) else None,
                            province=row['province'] if pd.notna(row['province']) else None,
                            lon=row['lon'] if pd.notna(row['lon']) else None,
                            lat=row['lat'] if pd.notna(row['lat']) else None,
                            variety=row['Variety'] if pd.notna(row['Variety']) else None,
                            season_type=row['Season_type'] if pd.notna(row['Season_type']) else None,
                            opt_date=row['Opt_date'] if pd.notna(row['Opt_date']) else None,
                            planting_option=int(row['Planting_Option']) if pd.notna(row['Planting_Option']) else None,
                            check_sum=checksum
                        )
                        crop_data_records.append(record)
                    else:
                        logger.warning(f"Skipping row {index} from {file_name} due to empty coordinates")

                    if len(crop_data_records) >= batch_size:
                        crop_data_repo.batch_insert(crop_data_records)
                        logger.info(f"Processed batch of {len(crop_data_records)} records from {file_name}")
                        crop_data_records.clear()  # Clear the batch

            # Insert remaining records
            if crop_data_records:
                logger.info(f"Inserting final batch of {len(crop_data_records)} records")
                crop_data_repo.batch_insert(crop_data_records)
                crop_data_records.clear()

            processed_file = ProcessedFiles(
                file_name=file_name,
                check_sum=checksum
            )
            processed_files_repo.add_processed_file(processed_file=processed_file)
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


def load_rds_to_db(data_folder: str, batch_size: int = 1000, chunk_size: int = 10000):
    """
    Loads and processes all RDS files from a specified directory by submitting them for processing
    using a process pool executor. Each file is processed in a separate process.

    Remote RDS files defined in the REMOTE_RDS_URLS env var are downloaded first.

    Args:
        data_folder (str): The directory containing the RDS files to be processed.
        batch_size (int): The number of records to batch insert into the database. Defaults to 1000.
        chunk_size (int): The number of rows to read at a time from each RDS file. Defaults to 10000.
    """
    os.makedirs(data_folder, exist_ok=True)
    global_start_time = time.time()

    download_remote_files(data_folder)

    file_paths = [os.path.join(data_folder, f) for f in os.listdir(data_folder) if f.endswith('.RDS')]

    logger.info(f"Starting to process {len(file_paths)} file(s) from {data_folder}")

    with app.app_context():
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(lambda file_path: process_file(file_path, batch_size, chunk_size), file_paths)

    global_elapsed_time = time.time() - global_start_time
    if global_elapsed_time > 60:
        minutes, seconds = divmod(global_elapsed_time, 60)
        logger.info(f"Processing all files took {int(minutes)} minutes and {seconds:.2f} seconds")
    else:
        logger.info(f"Processing all files took {global_elapsed_time:.2f} seconds")


if __name__ == '__main__':
    rds_folder = os.path.join("static/", 'data')
    load_rds_to_db(data_folder=rds_folder, batch_size=2000, chunk_size=10000)
