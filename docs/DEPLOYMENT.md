# Deployment Guide

Covers Docker Compose setup, image builds, service configuration, and running management commands in containers.

---

## 1. Architecture

The `docker-compose.yml` defines two services:

| Service | Image | Purpose |
|---|---|---|
| `kvuno` | `masgeek/kvuno-api` (built from `Dockerfile`) | Flask API on port 5000 |
| `db` | `postgres:17-alpine` | PostgreSQL database on port 5432 |

```
┌──────────────┐      port 5432     ┌──────────────┐
│   db         │◀───────────────────│   kvuno      │
│  PostgreSQL  │   DB_HOST=db       │  Flask API   │
│  17-alpine   │                    │  port 5000   │
└──────────────┘                    └──────┬───────┘
                                           │ port 5000
                                           ▼
                                      Host / Client
```

A named volume `pgdata` persists database data across restarts.

---

## 2. Environment Variables

### `docker-compose.yml` interpolation

The compose file reads these variables from the host environment (or `.env` file in the project root):

| Compose variable | Default | Used by |
|---|---|---|
| `TAG` | `latest` | Docker image tag |
| `DB_NAME` | `agwise_api` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASS` | `postgres` | Database password |

### Required `.env` for the app container

The `kvuno` service loads `.env` at runtime (via `load_dotenv()` in `app/__init__.py`). You must set:

```env
# Build the DB URL from parts (app.config.build_db_url)
DB_DRIVER=postgresql
DB_HOST=db                   # ← service name, not localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=agwise_api

# Optional: full URL override
# DB_URL=postgresql://postgres:postgres@db:5432/agwise_api
```

> **Important:** When running inside Docker Compose, `DB_HOST` must be `db` (the service name), not `127.0.0.1` or `localhost`, because containers communicate over the internal Compose network.

---

## 3. Running

### First-time startup

```bash
# Build images and start both services in the background
docker compose up --build -d

# Run database migrations
docker compose exec kvuno alembic upgrade head

# Verify health
curl http://localhost:5000/health
```

### Normal start/stop

```bash
docker compose up -d          # Start services
docker compose logs -f        # Follow logs
docker compose down           # Stop and remove containers (data persists)
docker compose down -v        # Stop and delete volumes (wipes DB)
```

### Rebuilding after dependency changes

```bash
docker compose build --no-cache kvuno
docker compose up -d
```

---

## 4. Running Commands Inside Containers

### Database migrations

```bash
docker compose exec kvuno alembic upgrade head
docker compose exec kvuno alembic revision --autogenerate -m "description"
```

### Housekeeping (RDS ingestion)

```bash
# Copy RDS files into the container first, then run:
docker cp data/file.RDS kvuno:/app/static/data/
docker compose exec kvuno python housekeeping.py

# Or download remote files directly inside the container:
docker compose exec kvuno python app/utils/downloader.py <URL>
```

### Interactive shell

```bash
docker compose exec kvuno bash
docker compose exec db psql -U postgres -d agwise_api
```

---

## 5. Image Variants

### Dev (`Dockerfile`)

- Base: `python:3.12-slim`
- Installs **all** dependencies (including dev)
- Runs the Flask dev server via `python run.py`
- Suitable for local development and testing

### Production (`Dockerfile.prod.dockerfile`)

- Base: `python:3.12-slim`
- Installs **only** production dependencies (`poetry install --no-dev`)
- Copies code into the image (no volume mount needed)
- Runs Gunicorn as the WSGI server
- No volume mount — suitable for deployment to a registry

To build and run the production image standalone:

```bash
docker build -f Dockerfile.prod.dockerfile -t kvuno-api:latest .
docker run -p 5000:5000 --env-file .env kvuno-api:latest
```

To use the production image with Compose, create a `docker-compose.prod.yml`:

```yaml
services:
  kvuno:
    image: masgeek/kvuno-api:latest
    build:
      context: .
      dockerfile: Dockerfile.prod.dockerfile
    volumes: []    # ← no volume mount in production
    # ... rest same as docker-compose.yml
```

---

## 6. Volumes

| Volume | Mount point | Purpose |
|---|---|---|
| `pgdata` | `/var/lib/postgresql/data` | Persists database files across restarts |

To inspect or backup the database volume:

```bash
docker run --rm -v kvuno_pgdata:/data -v $(pwd):/backup alpine tar czf /backup/pgdata.tar.gz -C /data .
```

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| API returns 500 on `/health` | DB connection refused | Check `DB_HOST=db` (not `localhost`) in `.env` |
| `psycopg2.OperationalError` | PostgreSQL not ready yet | Wait a few seconds or add `depends_on` healthcheck |
| Migrations fail with "no such table" | Alembic not yet run | Run `docker compose exec kvuno alembic upgrade head` |
| Port 5432 already in use | Local PostgreSQL running | Stop local PG or change the host-side port: `ports: - "5433:5432"` |
| Port 5000 already in use | Another service on port 5000 | Stop the other service or change: `ports: - "5001:5000"` |

### Wait for PostgreSQL to be ready

Add this to the `kvuno` service in `docker-compose.yml` to prevent race conditions on first boot:

```yaml
  kvuno:
    depends_on:
      db:
        condition: service_healthy

  db:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
```
