import os

from dotenv import load_dotenv

from app.celery_app import celery_app
from app.config import build_db_url
from app.models.database_conn import MyDb

load_dotenv()

_worker_app = None


def _get_worker_app():
    global _worker_app
    if _worker_app is None:
        from flask import Flask
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = build_db_url()
        app.config['SQLALCHEMY_ECHO'] = os.getenv('DEBUG_DB', 'false').lower() == 'true'
        MyDb.init_app(app)
        _worker_app = app
    return _worker_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_file_task(self, file_path: str):
    app = _get_worker_app()
    with app.app_context():
        from app.services.housekeeper import process_file, housekeeping_settings, set_app
        set_app(app)
        process_file(file_path=file_path, **housekeeping_settings())


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_pending_task(self):
    app = _get_worker_app()
    with app.app_context():
        from app.services.housekeeper import load_rds_to_db, set_app, DATA_DIR, housekeeping_settings
        set_app(app)
        load_rds_to_db(data_folder=DATA_DIR, **housekeeping_settings())
