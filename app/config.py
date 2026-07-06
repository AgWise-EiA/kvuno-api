import os


APP_NAME="KVuno API"
APP_VERSION="1.0.0"
API_PREFIX = "/api"
API_VERSION = "/v1"


def build_db_url() -> str:
    """
    Build a database URL from individual environment variables.

    If DB_URL is set, it is returned as-is (backwards compatibility).

    Otherwise the URL is built from:
      DB_DRIVER (default: postgresql)
      DB_HOST   (default: 127.0.0.1)
      DB_PORT   (default: 5432)
      DB_USER   (default: postgres)
      DB_PASSWORD (default: postgres)
      DB_NAME   (default: agwise_api)

    For SQLite only DB_NAME is used (default: kvuno.db).
    """
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
