# KVuno API

A Flask-based REST API for processing agricultural RDS (R Data Serialization) files containing crop planting data. It extracts optimized sowing dates, crop varieties, and geographic coordinates from RDS files, loads them into a database (SQLite/MySQL/PostgreSQL), and serves the data through a paginated, filterable API endpoint. Duplicate files are tracked via checksums to avoid re-imports.

Built for the [AgWISE-EiA](https://agwise.cgiar.org) initiative (Alliance for a Green Revolution in Africa / Excellence in Agronomy).

## Features

- **RDS File Ingestion** — Reads `.RDS` files using `pyreadr`, processes data in chunks with batch inserts
- **Deduplication** — SHA-256 checksums track processed files to prevent duplicate imports
- **Concurrent Processing** — Uses `ThreadPoolExecutor` for parallel RDS file ingestion
- **REST API** — OpenAPI 3.0 compliant, auto-generated docs at `/openapi`
- **Paginated & Filterable Queries** — Filter by coordinates + radius, country, province, variety, season type, optimal date, planting option
- **Spatial Data Support** — PostGIS `POINT` geometry (SRID 4326) with `ST_DWithin` radius filtering
- **Multi-Database** — SQLite, MySQL, PostgreSQL compatible
- **Health Check** — `GET /health` endpoint with database connectivity status
- **Dockerized** — Dev and production Dockerfiles with docker-compose (PostgreSQL)
- **Database Migrations** — Alembic-managed schema evolution
- **CORS** — Cross-origin support enabled globally
- **Request Rate Limiting** — Flask-Limiter available for route protection

## Tech Stack

| Component | Technology |
|---|---|
| Framework | Flask (via flask-openapi3) |
| ORM | SQLAlchemy (flask-sqlalchemy) |
| Database | SQLite / PostgreSQL (psycopg2) |
| Migrations | Alembic |
| Spatial | GeoAlchemy2 / PostGIS |
| RDS Parsing | pyreadr + pandas |
| Logging | loguru |
| Serving | Waitress (dev) / Gunicorn (prod) |
| Containerization | Docker + docker-compose |
| CI/CD | GitHub Actions |

## Project Structure

```
kvuno/
├── app/
│   ├── __init__.py           # Application factory (Flask OpenAPI)
│   ├── config.py             # App constants and configuration
│   ├── gunicorn_config.py    # Gunicorn server configuration
│   ├── api/
│   │   ├── planting_data.py  # Planting data API blueprint
│   │   └── user.py           # User auth API blueprint (stubs)
│   ├── dto/
│   │   ├── crop_data_resp.py # Response DTOs (Pydantic models)
│   │   └── data_filters.py   # Filter DTOs with validation
│   ├── models/
│   │   ├── database_conn.py  # Database connection manager
│   │   └── kvuno.py          # SQLAlchemy ORM models
│   ├── repo/
│   │   ├── crop_data.py      # CropData repository (CRUD + filtering)
│   │   └── processed_files.py # ProcessedFiles repository
│   ├── routes/
│   │   └── main.py           # App routes (/, /health)
│   └── utils/
│       ├── logging.py        # SharedLogger (loguru wrapper)
│       └── migration_utils.py# Dialect-aware column utilities
│
├── alembic/                  # Database migration scripts
│   └── versions/             # Migration versions
│
├── logs/                     # Log output directory
├── static/data/              # RDS data files for ingestion
│
├── .env.example              # Environment variable template
├── docker-compose.yml        # Multi-service Docker setup
├── Dockerfile                # Dev Docker image
├── Dockerfile.prod.dockerfile# Production Docker image
├── housekeeping.py           # RDS file processing ETL script
├── model-generator.py        # ORM model code generator
├── pyproject.toml            # Project metadata and dependencies
├── run.py                    # Dev server entry point
└── wsgi.py                   # WSGI entry point for Gunicorn
```

## Installation

### Prerequisites

- Python 3.13+
- Poetry (`pip install poetry`)

### Setup

```bash
# Clone the repository
git clone git@github.com:AgWISE-EiA/kvuno-api.git
cd kvuno-api

# Install dependencies
poetry install

# Copy environment variables
cp .env.example .env
```

Edit `.env` with your database connection. You can either set a full `DB_URL` or individual parts:

```env
# Full URL (takes priority)
# DB_URL="postgresql://user:pass@host:5432/kvuno"

# Individual parts
DB_DRIVER=postgresql
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=agwise_api

# For SQLite:
# DB_DRIVER=sqlite
# DB_NAME=kvuno.db
```

### Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Create a new migration (after model changes)
alembic revision --autogenerate -m "description"
```

### Running the Application

```bash
# Development server
python run.py

# Production with Gunicorn
gunicorn wsgi:app -c app/gunicorn_config.py
```

The API will be available at `http://localhost:5000` and the OpenAPI docs at `http://localhost:5000/openapi`.

### Docker Deployment

A `docker-compose.yml` runs the Flask API alongside PostgreSQL with a single command:

```bash
# Build and start both services
docker compose up --build -d

# Run database migrations
docker compose exec kvuno alembic upgrade head

# Verify
curl http://localhost:5000/health
```

Two image variants are provided:
- **`Dockerfile`** — dev image with Flask dev server
- **`Dockerfile.prod.dockerfile`** — production image with Gunicorn

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full details on Compose configuration, environment variables, running commands inside containers, and troubleshooting.

## Usage

### Ingesting RDS Data

Place `.RDS` files in `static/data/` and run:

```bash
python housekeeping.py
```

This will:
1. Compute a SHA-256 checksum for each file
2. Skip files that have already been processed
3. Parse RDS data with `pyreadr`
4. Batch-insert records into the database

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Redirects to `/openapi` (Swagger UI) |
| `GET` | `/health` | Health check with database status |
| `GET` | `/api/v1/planting-data/` | Paginated, filterable crop data |
| `POST` | `/api/v1/users/register` | User registration (stub) |
| `POST` | `/api/v1/users/login` | User login (stub) |

### Query Parameters for `/api/v1/planting-data/`

| Parameter | Type | Description |
|---|---|---|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Items per page (default: 10) |
| `coordinates` | string | Center point for radius search (`lon,lat`) |
| `radius` | float | Search radius in meters (requires `coordinates`) |
| `country` | string | Country name (partial ILIKE match) |
| `province` | string | Province name (partial ILIKE match) |
| `variety` | string | Crop variety exact match |
| `season_type` | string | Season type exact match |
| `opt_date` | string | Optimal sowing date (`YYYY-MM-DD`) |
| `planting_option` | string | Planting option exact match |

### Response Format

```json
{
  "data": [
    {
      "id": 1,
      "coordinates": {"lat": -17.85, "lon": 25.92},
      "country": "Zambia",
      "province": "Southern",
      "variety": "Soybean",
      "season_type": "Main",
      "opt_date": "2024-11-15",
      "planting_option": "Option A"
    }
  ],
  "pagination": {
    "total": 42,
    "pages": 5,
    "current_page": 1,
    "per_page": 10
  }
}
```

## Configuration

Key environment variables (see `.env.example`):

| Variable | Description | Default |
|---|---|---|
| `DB_URL` | Full database connection string (overrides DB_*) | — |
| `DB_DRIVER` | Database driver | `postgresql` |
| `DB_HOST` | Database host | `127.0.0.1` |
| `DB_PORT` | Database port | `5432` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `postgres` |
| `DB_NAME` | Database name | `agwise_api` |
| `FLASK_DEBUG` | Enable debug mode | `1` |
| `SERVER_HOST` | Bind address | `0.0.0.0` |
| `SERVER_PORT` | Bind port | `5000` |
| `LOG_LEVEL` | Logging level | `DEBUG` |
| `SERVER_URL_PROD` | Production server URL | — |

## CI/CD

GitHub Actions workflows:

- **PR Checks** — Runs Ruff linting and pytest on pull requests
- **Version Bumping** — Automated version tags on main
- **Auto PR** — Creates release PRs from version bumps
- **TODO Scanner** — Scans codebase for TODO/FIXME markers

## License

Project maintained by [masgeek](mailto:barsamms@gmail.com) as part of the AgWISE-EiA initiative.
