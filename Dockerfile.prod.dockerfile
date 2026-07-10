FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN pip install poetry==2 --no-cache-dir

WORKDIR /app

#COPY pyproject.toml poetry.lock ./
COPY pyproject.toml ./

RUN poetry install --no-root --without dev --no-ansi

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/app

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app . .
RUN chown app:app /app

USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "--timeout", "60", "wsgi:app"]