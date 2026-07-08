FROM node:24-alpine AS frontend
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@latest --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN pip install poetry==2 --no-cache-dir

WORKDIR /app

#COPY pyproject.toml poetry.lock ./
COPY pyproject.toml ./

RUN poetry install --no-root --no-ansi

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/app

# Match these to your host user (id -u / id -g) at build time so bind-mounted
# files keep correct ownership. Defaults below match the common single-user
# Linux/macOS UID/GID of 1000.
ARG UID=1000
ARG GID=1000

RUN groupadd -g ${GID} app && \
    useradd -u ${UID} -g app -d /app -s /bin/bash app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=frontend /app/node_modules /app/node_modules
COPY --chown=app:app . .
RUN chown app:app /app

USER app

EXPOSE 5000

CMD ["python3", "run.py"]