"""File upload API for ingesting RDS/Parquet files into the database."""
import os
import uuid

from flask import request
from flask_openapi3 import Tag, APIBlueprint

from app.config import API_PREFIX, API_VERSION
from app.dto.upload import UploadResponse
from app.tasks import process_file_task as process_file

__bp__ = "/data"
url_prefix = API_PREFIX + API_VERSION + __bp__

tag = Tag(name="ingestion", description="File upload and data ingestion")
api = APIBlueprint(__bp__, __name__, url_prefix=url_prefix, abp_tags=[tag])

DATA_DIR = os.getenv('HOUSEKEEPING_DATA_DIR', os.path.join("static", "data"))

ALLOWED_EXTENSIONS = {'.rds', '.parquet'}


@api.post('/upload', responses={202: UploadResponse})
def upload_file():
    """Upload an RDS or Parquet file for processing.

    The file is saved to the housekeeping data directory and processed
    in the background.
    """
    if 'file' not in request.files:
        return {"error": "No file provided"}, 400

    f = request.files['file']
    if not f.filename:
        return {"error": "Empty filename"}, 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"error": f"Unsupported extension {ext}. Allowed: {ALLOWED_EXTENSIONS}"}, 400

    os.makedirs(DATA_DIR, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(DATA_DIR, unique_name)
    f.save(dest)

    process_file.delay(file_path=dest)

    return {"message": "File accepted for processing", "file": unique_name}, 202
