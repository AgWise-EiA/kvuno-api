import os

from dotenv import load_dotenv
from flask_cors import CORS
from flask_openapi3 import OpenAPI, Server, Contact, License, Info

from alembic import command
from alembic.config import Config as AlembicConfig

from app.models.database_conn import MyDb
from app.routes.main import register_app_routes
from app.config import build_db_url, APP_NAME, APP_VERSION

# Load environment variables from .env file
load_dotenv()

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


def run_migrations():
    """Run pending Alembic migrations at startup."""
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", build_db_url())
    command.upgrade(alembic_cfg, "head")


def register_apis(app: OpenAPI):
    """Register all API Blueprints with the Flask app."""
    from app.api.user import api as user_api
    from app.api.planting_data import api as planting_data_api
    from app.api.upload import api as upload_api

    app.register_api(user_api)
    app.register_api(planting_data_api)
    app.register_api(upload_api)


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
    CORS(app)

    # Configure the database URI
    app.config['SQLALCHEMY_DATABASE_URI'] = build_db_url()
    app.config['SQLALCHEMY_ECHO'] = os.getenv('DEBUG_DB', 'false').lower() == 'true'
    app.json.sort_keys = os.getenv('SORT_JSON') == '1'

    # Initialize the database
    init_db(app)

    # Run pending Alembic migrations
    with app.app_context():
        run_migrations()

    # Register APIs and other routes
    register_apis(app)
    register_app_routes(app)

    # Start background processing of any unprocessed files
    if os.getenv('HOUSEKEEPING_ENABLED', 'false').lower() == 'true':
        with app.app_context():
            from app.services.housekeeper import process_pending
            process_pending(app)

    return app
