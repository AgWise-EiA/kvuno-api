# Security Analysis & Recommendations

## Overview

This document describes the current security posture of the KVuno API, identifies findings discovered during a full codebase review, and provides actionable recommendations.

---

## Executive Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| CRITICAL | 1 | Authentication is entirely stubbed — passwords accepted but never hashed or stored |
| HIGH     | 2 | Path traversal in `/npm/<path>` route; no auth on any data/upload endpoint |
| MEDIUM   | 5 | Permissive CORS, SSRF potential in remote downloader, missing file size limits, `.env.example` leaks a token, path traversal in progress endpoint |
| LOW      | 6 | Default credentials, unbounded pagination, SSE queue exhaustion, auto-migration risks, credential logging, unauthenticated Redis |

---

## Detailed Findings

### CRITICAL

#### 1. Authentication is a no-op placeholder

**File:** `app/api/user.py`, `app/dto/auth.py`

Both `/api/v1/users/register` and `/api/v1/users/login` return hardcoded success responses. The `password` field is accepted in the request DTO but is **never validated, hashed, or stored**. The security schemes (`basic`, `jwt`) declared in the OpenAPI spec at `app/__init__.py:93-98` are never enforced by any middleware or decorator.

**Risk:** Any caller can register or "authenticate" as any user with no credentials. There is no access control anywhere in the application.

**Remediation:** Implement authentication before deploying to any environment that requires access control. See [Recommendations](#recommendations) below.

---

### HIGH

#### 2. Path traversal in `/npm/<path>` route

**File:** `app/routes/main.py:162-165`

```python
@app.route('/npm/<path:filename>')
def npm_serve(filename):
    nm = os.path.join(os.path.dirname(...), '..', 'node_modules')
    return send_from_directory(nm, filename)
```

While `send_from_directory` provides some protection, `<path:filename>` can contain `..` sequences. A request like `GET /npm/../app/config.py` could leak source files outside `node_modules/`.

**Risk:** Source code disclosure (configuration, credentials, business logic).

**Remediation:**

```python
from werkzeug.utils import safe_join

@app.route('/npm/<path:filename>')
def npm_serve(filename):
    nm = os.path.join(os.path.dirname(...), '..', 'node_modules')
    safe = safe_join(nm, filename)
    if safe is None or not safe.startswith(os.path.realpath(nm)):
        return abort(404)
    return send_from_directory(nm, filename)
```

Or remove this route in production and serve static assets via nginx/CDN.

#### 3. No authentication on any endpoint

**Files:** `app/api/upload.py`, `app/api/planting_data.py`, `app/routes/main.py`

All API and UI routes are publicly accessible. The `planting_data` endpoint serves data to anyone, the upload endpoint accepts files from anyone, and the UI routes expose job progress and processing controls.

**Risk:** Data exfiltration, arbitrary file upload, denial of service.

**Remediation:** Implement authentication middleware (see [Recommendations](#recommendations)) and apply it to endpoints that require protection.

---

### MEDIUM

#### 4. CORS allows all origins

**File:** `app/__init__.py:85`

```python
CORS(app)
```

Without any arguments, Flask-CORS allows requests from any origin with any header.

**Risk:** Any website can make cross-origin requests to the API (though no auth tokens exist to steal in the current state).

**Remediation:**

```python
CORS(app, origins=["https://example.com"], supports_credentials=True)
```

#### 5. SSRF potential in remote downloader

**Files:** `app/services/housekeeper.py:190-235`, `app/utils/downloader.py`

The `REMOTE_RDS_URLS` environment variable can contain arbitrary URLs. The downloader fetches these URLs with `requests.get()`. If an attacker can influence this env var, they could target internal network hosts.

**Risk:** Server-side request forgery against internal services (Redis, database, cloud metadata endpoints).

**Remediation:**
- Validate that URLs are HTTPS and match an allow-list of domains.
- Disable redirects (`allow_redirects=False`) or validate redirect targets.
- Do not log the full URL (auth tokens may be embedded).

#### 6. No file size limit on upload

**File:** `app/api/upload.py`

The `MAX_FILE_SIZE_MB` variable is only used by the UI upload page as a client-side hint. The API endpoint has no application-level size enforcement.

**Risk:** An attacker can upload arbitrarily large files, causing disk exhaustion or DoS.

**Remediation:**

```python
from flask import request
from werkzeug.utils import secure_filename

MAX_SIZE = int(os.getenv('MAX_FILE_SIZE_MB', 20)) * 1024 * 1024

# Before saving
if request.content_length and request.content_length > MAX_SIZE:
    return {"error": "File too large"}, 413
```

#### 7. `.env.example` contains a real token

**File:** `.env.example:30`

The example `REMOTE_RDS_URLS` value contains a valid `_xsrf` authentication token in the URL query string.

**Risk:** Anyone with access to the repository can use this token to authenticate against the remote service.

**Remediation:** Replace the example URL with a placeholder like `https://example.com/data/file.RDS`.

#### 8. Path traversal in `/ui/progress/<file_name>`

**File:** `app/routes/main.py:283-292`

```python
@app.route('/ui/progress/<file_name>')
def ui_progress(file_name):
    file_path = os.path.join(DATA_DIR, file_name)
    progress_path = file_path + '.progress.json'
```

The `file_name` parameter is user-controlled and used directly in `os.path.join`. A request like `/ui/progress/../../etc/passwd` would read `/etc/passwd.progress.json` (which would not exist), but `/ui/progress/../../app/config.py` would attempt to read `app/config.py.progress.json`. While the `.progress.json` suffix limits exploitation, the path is still constructed unsafely.

**Remediation:**

```python
from pathlib import Path
from werkzeug.exceptions import NotFound

data_dir = Path(DATA_DIR).resolve()
file_path = (data_dir / file_name).resolve()
if not str(file_path).startswith(str(data_dir)):
    raise NotFound()
```

---

### LOW

#### 9. Weak default database credentials

**File:** `app/config.py:22-23`

```python
'DB_USER': os.getenv('DB_USER', 'postgres'),
'DB_PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
```

If env vars are unset, the application connects with `postgres/postgres`.

**Remediation:** Remove default values so the application fails fast if credentials are missing:

```python
'DB_USER': os.environ['DB_USER'],
'DB_PASSWORD': os.environ['DB_PASSWORD'],
```

#### 10. Dev server binds to all interfaces

**File:** `run.py:11`

```python
app.run(host="0.0.0.0", port=5000, debug=debug)
```

Exposes the development server to the network. Acceptable for development but should be flagged for production.

#### 11. Auto-migration at startup

**File:** `app/__init__.py:167`

```python
if os.getenv('RUN_MIGRATIONS', 'true').lower() == 'true':
    with app.app_context():
        run_migrations()
```

Running migrations automatically at startup can cause issues in multi-replica deployments (multiple instances racing to migrate).

**Remediation:** Disable auto-migration in production. Run migrations as a separate deploy step.

#### 12. Unbounded SSE client queue

**File:** `app/routes/main.py:42-53`

Each SSE client gets a queue entry in `_sse_queues`. If clients connect but never read, the queue fills up and entries accumulate.

**Remediation:** Set a maximum number of concurrent SSE connections and implement a read timeout.

#### 13. Pagination parameters have no upper bound

**File:** `app/api/planting_data.py`

The `per_page` parameter is used directly in SQLAlchemy `paginate()`. Very large values could cause excessive memory usage.

**Remediation:**

```python
per_page = min(int(request.args.get('per_page', 50)), 500)
```

#### 14. URL with auth token logged at INFO level

**File:** `app/utils/downloader.py`

```python
logger.info(f"Downloading {url}")
```

If the URL contains embedded credentials or tokens (as in the `REMOTE_RDS_URLS` pattern), they are written to logs.

**Remediation:**

```python
from urllib.parse import urlparse, urlunparse

sanitized = urlunparse(urlparse(url)._replace(query=''))
logger.info(f"Downloading {sanitized}")
```

#### 15. Redis without authentication

**File:** `app/celery_app.py`

```python
'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
```

No password is required to connect to Redis. If Redis is exposed on the network, an attacker can inject arbitrary Celery tasks.

**Remediation:** Use a Redis password and configure it via `CELERY_BROKER_URL`:

```
CELERY_BROKER_URL=redis://:password@redis:6379/0
```

---

## Recommendations by Priority

### Immediate (before production deployment)

1. **Replace placeholder auth with real authentication.** Use Flask-HTTPAuth, Flask-JWT-Extended, or a similar library. Hash passwords with `bcrypt` or `argon2`.
2. **Fix the `/npm/<path>` traversal** by either removing the route in production or adding `safe_join` validation.
3. **Remove the real token from `.env.example`.**
4. **Add file size enforcement** to the upload endpoint.

### Short-term

5. **Restrict CORS** to known origins.
6. **Add input validation** to `/ui/progress/<file_name>` and `/ui/process`.
7. **Sanitize URLs in logs** to avoid leaking embedded credentials.
8. **Add rate limiting** to upload and data endpoints (Flask-Limiter is already a dependency).

### Medium-term

9. **Implement authentication middleware** and apply it selectively to endpoints.
10. **Add SSRF protections** to the remote downloader (domain allow-list, disable redirects).
11. **Configure Redis authentication.**
12. **Add pagination upper bounds.**
13. **Set a max SSE client limit.**

### Long-term

14. **Disable auto-migration** in production and use a separate deploy step.
15. **Add Content Security Policy (CSP) headers** to UI pages.
16. **Add dependency vulnerability scanning** (e.g., `pip audit`, `pnpm audit`) to CI.
17. **Consider adding API keys** for programmatic access to upload/query endpoints.

---

## Existing Security Controls

The codebase already includes some positive security patterns worth highlighting:

| Control | Location |
|---------|----------|
| File extension validation | `app/routes/main.py:220`, `app/api/upload.py:40-42` |
| UUID-based filenames (prevents name collision/traversal) | `app/routes/main.py:223`, `app/api/upload.py:46` |
| Checksum deduplication (SHA-256) | `app/utils/__init__.py` |
| Pydantic input validation with coordinate bounds checks | `app/dto/data_filters.py` |
| Parameterized SQL queries (SQLAlchemy ORM) | All `repo/*.py` files |
| Graceful shutdown on SIGTERM/SIGINT | `app/services/housekeeper.py:84-104` |
| Resumable chunked uploads (no oversized in-memory buffers) | `app/routes/main.py:190-206` |
| Dry-run mode for batch processing | `app/services/housekeeper.py:491` |
| Server header hidden in gunicorn | `app/gunicorn_config.py` |
