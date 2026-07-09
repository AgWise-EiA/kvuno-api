import os


APP_NAME="KVuno API"
APP_VERSION="1.0.0"
API_PREFIX = "/api"
API_VERSION = "/v1"

# ── Database ───────────────────────────────────────────────────

def build_db_url() -> str:
    """Build a database URL from individual environment variables."""
    url = os.getenv("DB_URL")
    if url:
        return url

    driver = os.getenv("DB_DRIVER", "postgresql")
    if driver == "sqlite":
        name = os.getenv("DB_NAME", "kvuno.db")
        return f"sqlite:///{name}"

    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    name = os.getenv("DB_NAME", "agwise_api")

    return f"{driver}://{user}:{password}@{host}:{port}/{name}"


# ── Celery / Redis ─────────────────────────────────────────────

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_DEFAULT_QUEUE = os.getenv('CELERY_TASK_DEFAULT_QUEUE', 'kvuno')
CELERY_TASK_MAX_RETRIES = int(os.getenv('CELERY_TASK_MAX_RETRIES', '10'))
CELERY_TASK_RETRY_DELAY = int(os.getenv('CELERY_TASK_RETRY_DELAY', '60'))


def celery_broker_available() -> bool:
    """Check if the Redis/Celery broker host:port is reachable."""
    from urllib.parse import urlparse
    import socket
    parts = urlparse(CELERY_BROKER_URL)
    host = parts.hostname or 'localhost'
    port = parts.port or 6379
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except (OSError, ValueError):
        return False


# ── Housekeeping / ingestion ───────────────────────────────────

HOUSEKEEPING_ENABLED = os.getenv('HOUSEKEEPING_ENABLED', 'false').lower() == 'true'
HOUSEKEEPING_DATA_DIR = os.getenv('HOUSEKEEPING_DATA_DIR', os.path.join('static', 'data'))
HOUSEKEEPING_BATCH_SIZE = int(os.getenv('HOUSEKEEPING_BATCH_SIZE', '2000'))
HOUSEKEEPING_CHUNK_SIZE = int(os.getenv('HOUSEKEEPING_CHUNK_SIZE', '5000'))
HOUSEKEEPING_CHECKPOINT_INTERVAL = int(os.getenv('HOUSEKEEPING_CHECKPOINT_INTERVAL', '50'))
HOUSEKEEPING_MAX_WORKERS = int(os.getenv('HOUSEKEEPING_MAX_WORKERS', '1'))
