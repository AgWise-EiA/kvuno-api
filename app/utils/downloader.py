"""
Utility for downloading RDS files from remote sources.
Supports authenticated downloads with session cookies, bearer tokens, and custom headers.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

from app.utils.logging import SharedLogger
import logging

_shared_logger = SharedLogger(level=logging.DEBUG)
_logger = _shared_logger.get_logger()

DEFAULT_DATA_DIR = os.path.join("static", "data")


class RDSDownloader:
    """Downloads RDS files from remote servers with authentication support."""

    def __init__(self, data_dir: Optional[str] = None, logger=None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self.session = requests.Session()
        self.logger = logger or _logger

    def set_bearer_token(self, token: str):
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def set_cookies(self, cookies: dict):
        self.session.cookies.update(cookies)

    def set_headers(self, headers: dict):
        self.session.headers.update(headers)

    def set_basic_auth(self, username: str, password: str):
        self.session.auth = (username, password)

    def download(self, url: str, filename: Optional[str] = None) -> str:
        """
        Download an RDS file from a remote URL.

        Args:
            url: Remote URL of the RDS file (may include query params like _xsrf)
            filename: Optional custom filename (defaults to URL path basename)

        Returns:
            Absolute path to the downloaded file
        """
        from urllib.parse import urlparse, unquote

        start = time.time()
        parsed = urlparse(url)
        name = filename or os.path.basename(unquote(parsed.path))
        if not name.endswith(".RDS"):
            name += ".RDS"
        dest = os.path.abspath(os.path.join(self.data_dir, name))

        self.logger.info(f"Downloading {url}")
        self.logger.info(f"Destination: {dest}")

        try:
            resp = self.session.get(url, stream=True, timeout=300)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and downloaded % (1024 * 512) == 0:
                        pct = downloaded / total * 100
                        self.logger.debug(f"Downloaded {downloaded / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB ({pct:.0f}%)")

            elapsed = time.time() - start
            self.logger.info(f"Downloaded {name} ({downloaded / 1024 / 1024:.1f}MB) in {elapsed:.1f}s")
            return dest

        except requests.RequestException as e:
            self.logger.error(f"Download failed for {url}: {e}")
            if os.path.exists(dest):
                os.remove(dest)
            raise

    def download_batch(self, urls: list[str], filenames: Optional[list[str]] = None) -> list[str]:
        """Download multiple RDS files in sequence."""
        paths = []
        for i, url in enumerate(urls):
            name = filenames[i] if filenames and i < len(filenames) else None
            paths.append(self.download(url, filename=name))
        return paths


def download_and_process(url: str, filename: Optional[str] = None,
                         data_dir: Optional[str] = None,
                         token: Optional[str] = None,
                         cookies: Optional[dict] = None,
                         headers: Optional[dict] = None,
                         process: bool = True,
                         batch_size: int = 2000,
                         chunk_size: int = 10000,
                         logger=None) -> str:
    """
    Download an RDS file and optionally process it into the database.

    Args:
        url: Remote URL of the RDS file
        filename: Optional custom filename
        data_dir: Directory to save the file (defaults to static/data)
        token: Optional Bearer token for authentication
        cookies: Optional cookies dict for session auth
        headers: Optional custom HTTP headers
        process: If True, run housekeeping on the downloaded file
        batch_size: Batch size for DB insertion (if processing)
        chunk_size: Chunk size for RDS parsing (if processing)
        logger: Optional logger instance (uses module logger if not provided)

    Returns:
        Path to the downloaded file
    """
    downloader = RDSDownloader(data_dir=data_dir, logger=logger)
    if token:
        downloader.set_bearer_token(token)
    if cookies:
        downloader.set_cookies(cookies)
    if headers:
        downloader.set_headers(headers)

    filepath = downloader.download(url, filename=filename)

    if process:
        from housekeeping import process_file
        process_file(filepath, batch_size=batch_size, chunk_size=chunk_size)

    return filepath


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download RDS files from remote sources")
    parser.add_argument("urls", nargs="+", help="Remote RDS file URL(s)")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Directory to save files")
    parser.add_argument("--token", help="Bearer token for authentication")
    parser.add_argument("--cookie", action="append", help="Cookie in KEY=VALUE format (repeatable)")
    parser.add_argument("--header", action="append", help="Header in KEY:VALUE format (repeatable)")
    parser.add_argument("--process", action="store_true", help="Process downloaded files into the database")
    parser.add_argument("--batch-size", type=int, default=2000, help="Batch size for DB inserts")
    parser.add_argument("--chunk-size", type=int, default=10000, help="Chunk size for RDS parsing")

    args = parser.parse_args()

    cookies = {}
    if args.cookie:
        for c in args.cookie:
            k, _, v = c.partition("=")
            cookies[k] = v

    headers = {}
    if args.header:
        for h in args.header:
            k, _, v = h.partition(":")
            headers[k.strip()] = v.strip()

    for url in args.urls:
        download_and_process(
            url,
            data_dir=args.data_dir,
            token=args.token,
            cookies=cookies or None,
            headers=headers or None,
            process=args.process,
            batch_size=args.batch_size,
            chunk_size=args.chunk_size,
        )
