import os

from dotenv import load_dotenv
from flask_cors import CORS
from flask_openapi3 import OpenAPI, Server, Contact, License, Info

from alembic import command
from alembic.config import Config as AlembicConfig

from pathlib import Path
import json
import shutil

from app.models.database_conn import MyDb
from app.routes.main import register_app_routes
from app.config import build_db_url, APP_NAME, APP_VERSION, HOUSEKEEPING_DATA_DIR, HOUSEKEEPING_ENABLED

# Load environment variables from .env file
load_dotenv()

def _cleanup_temp_files():
    data_dir = Path(HOUSEKEEPING_DATA_DIR)
    if not data_dir.is_dir():
        return

    import logging
    import time
    log = logging.getLogger(__name__)

    chunks_dir = data_dir / '.chunks'
    if chunks_dir.is_dir():
        shutil.rmtree(chunks_dir)
        log.info("Cleaned up chunks directory")

    raw = os.getenv('CLEANUP_AGE', '1d')
    unit = raw[-1]
    value = int(raw[:-1])
    multipliers = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    cutoff = time.time() - value * multipliers.get(unit, 86400)

    for p in data_dir.glob('*.progress.json'):
        try:
            with open(p) as f:
                job = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if job.get('status') != 'completed':
            continue
        if p.stat().st_mtime > cutoff:
            continue
        stem = p.stem.replace('.progress', '')
        for suffix in ('.rds', '.parquet', '.progress.json', '.meta.json', '.map.json'):
            target = data_dir / f"{stem}{suffix}"
            try:
                if target.is_file():
                    target.unlink()
                    log.info("Removed processed file: %s", target.name)
            except OSError:
                pass


# API contact information
contact = Contact(
    name="Munywele Sammy",
    email="sammy@munywele.co.ke",
    url="https://munywele.co.ke"
)

# API license information
api_license = License(
    name="Apache 2.0",
    identifier="Apache-2.0"
)

# API information
info = Info(
    title=APP_NAME,
    version=APP_VERSION,
    contact=contact,
    license=api_license,
    termsOfService="https://agwise.cgiar.org/terms-of-service"
)

# API servers
servers = [
    Server(url="http://127.0.0.1:5000"),
    Server(url=os.getenv("SERVER_URL_PROD", "https://kvuno.akilimo.org")),
]


def init_db(app):
    """Initialize the database with the Flask app."""
    MyDb.init_app(app)


def _db_available() -> bool:
    """Check if the database host:port is reachable (non-blocking)."""
    from urllib.parse import urlparse
    import socket
    url = build_db_url()
    if url.startswith('sqlite'):
        return True
    parts = urlparse(url)
    host = parts.hostname or '127.0.0.1'
    port = parts.port or 5432
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except (OSError, ValueError):
        return False


def run_migrations():
    """Run pending Alembic migrations at startup."""
    if not _db_available():
        import logging
        logging.warning(
            f"Database at {build_db_url()} is not reachable — skipping migrations. "
            f"Set RUN_MIGRATION=false to suppress this check."
        )
        return
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", build_db_url())
    command.upgrade(alembic_cfg, "head")


def register_apis(app: OpenAPI):
    """Register all API Blueprints with the Flask app."""
    from app.api.user import api as user_api
    from app.api.planting_data import api as planting_data_api
    from app.api.upload import api as upload_api
    from app.api.quality import api as quality_api

    app.register_api(user_api)
    app.register_api(planting_data_api)
    app.register_api(upload_api)
    app.register_api(quality_api)


def create_app():
    """Create and configure the Flask app."""
    app = OpenAPI(
        __name__,
        servers=servers,
        info=info,
        security_schemes={
            "basic": {"type": "http", "scheme": "basic"},
            "jwt": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    )

    # Enable Cross-Origin Resource Sharing (CORS)
    cors_origins = os.getenv('CORS_ORIGINS', 'http://127.0.0.1:5000')
    origins = [o.strip() for o in cors_origins.split(',') if o.strip()]
    CORS(app, origins=origins, supports_credentials=True)

    # Configure the database URI
    app.config['SQLALCHEMY_DATABASE_URI'] = build_db_url()
    app.config['SQLALCHEMY_ECHO'] = os.getenv('DEBUG_DB', 'false').lower() == 'true'
    app.json.sort_keys = os.getenv('SORT_JSON') == '1'

    # Initialize the database
    init_db(app)

    # Run pending Alembic migrations
    if os.getenv('RUN_MIGRATION', 'true').lower() == 'true':
        with app.app_context():
            run_migrations()

    @app.template_filter('datetime')
    def datetime_filter(ts):
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')

    # Register APIs and other routes
    register_apis(app)
    register_app_routes(app)

    # Clean up temporary files from previous runs
    with app.app_context():
        _cleanup_temp_files()

    # Enqueue background processing of any unprocessed files via Celery
    if HOUSEKEEPING_ENABLED:
        from app.services.housekeeper import process_pending
        process_pending()

    return app
