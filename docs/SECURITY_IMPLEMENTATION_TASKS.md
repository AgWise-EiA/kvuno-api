# Security Implementation Task List

This task list is derived from `docs/SECURITY.md` and is intended to guide remediation work before implementation begins.

## Immediate (✅ Complete)

- [x] Replace placeholder authentication in `app/api/user.py` and `app/dto/auth.py`.
- [x] Add persistent user storage (`User` + `UserToken` models, migration).
- [x] Hash passwords with `bcrypt`.
- [x] Validate credentials during login.
- [x] Return a Bearer token after successful login.
- [x] Add authentication tests for bcrypt hashing and token extraction.

- [x] Enforce authentication on protected endpoints.
- [x] Protect upload endpoints in `app/api/upload.py` (via `@require_auth`).
- [x] Protect UI processing and completion routes in `app/routes/main.py`.

- [x] Fix path traversal in `/npm/<path>` in `app/routes/main.py`.
- [x] Validate resolved paths with `safe_join`.
- [x] Reject requests that resolve outside `node_modules` (via `FLASK_ENV` guard).
- [x] Add traversal regression tests.

- [x] Remove the real token from `.env.example`.
- [x] Replace the `REMOTE_RDS_URLS` value with a placeholder URL.

- [x] Add server-side upload size enforcement in `app/api/upload.py`.
- [x] Enforce `MAX_FILE_SIZE_MB` on the server.
- [x] Return HTTP `413` for oversized requests.
- [x] Add upload size tests.

## Short-Term (✅ Complete)

- [x] Restrict CORS in `app/__init__.py` to configured origins.
- [x] Configure allowed origins from `CORS_ORIGINS` env var.
- [x] Avoid default allow-all behavior.

- [x] Validate paths in `/ui/progress/<file_name>` in `app/routes/main.py`.
- [x] Resolve requested files under `DATA_DIR` with traversal guard.
- [x] Return `404` for invalid or escaped paths.

- [x] Validate `/ui/process` inputs in `app/routes/main.py`.
- [x] Reject path traversal and unexpected file extensions.
- [x] Add tests for path safety and extension validation.

- [x] Sanitize URL logging in `app/utils/downloader.py`.
- [x] Strip query strings and credentials before logging.
- [x] Add unit tests for sanitized output.

- [x] Add rate limiting with Flask-Limiter.
- [x] Rate limit auth endpoints (10/h register, 20/h login).
- [x] Rate limit upload endpoint (10/h).
- [x] Rate limit public data endpoints (120/m).

## Medium-Term (✅ Complete)

- [x] Add SSRF protections to remote downloads.
- [x] Require HTTPS URLs (configurable via `REMOTE_RDS_ALLOW_HTTP`).
- [x] Add an allow-list of approved domains (`REMOTE_RDS_ALLOWED_DOMAINS`).
- [x] Disable redirects by default; validate redirect targets if followed.
- [x] Reject private, loopback, link-local, and metadata service addresses (socket resolution).
- [x] URL logging already sanitized.

- [x] Configure Redis authentication in `.env.example`.
- [x] Document password-based URL format: `redis://:password@host:port/db`.
- [x] Add Redis URL parsing tests.

- [x] Add pagination bounds in `app/api/planting_data.py` (`MAX_PER_PAGE=500`).
- [x] Clamp `per_page` to a safe maximum with `_clamp_per_page()`.
- [x] Add tests for high, low, and invalid pagination inputs.

- [x] Limit SSE clients in `app/routes/main.py`.
- [x] Add a maximum number of concurrent SSE connections (50).
- [x] Add 60-second read timeout with keepalive.
- [x] Clean up stale clients on disconnect.

## Long-Term (✅ Complete)

- [x] Disable automatic startup migrations in production.
- [x] Default to `RUN_MIGRATION=false` when `FLASK_ENV=production`.
- [x] Development environments still auto-migrate by default.

- [x] Add security headers for all responses.
- [x] Content Security Policy for HTML responses.
- [x] `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.
- [x] `Referrer-Policy: strict-origin-when-cross-origin`.
- [x] `Permissions-Policy`, `X-XSS-Protection`.

- [x] Add dependency vulnerability scanning to CI.
- [x] Python scanning via `pip-audit --strict` (blocks on high/critical).
- [x] JavaScript scanning via `pnpm audit` (non-blocking).

- [x] Foundation for API keys via `UserToken` model + Bearer token auth.
- [x] `@require_auth` decorator ready for machine client middleware.
- [x] Secure token generation via `secrets.token_hex(32)`.

## Verification Checklist (✅ All Passing)

- [x] Authentication and authorization tests pass (bcrypt hashing, token extraction).
- [x] Upload security tests pass (file size enforcement, extension validation).
- [x] Path traversal regression tests pass (npm_serve, ui_progress, ui_process).
- [x] Downloader SSRF and logging tests pass (6 SSRF validation tests, URL sanitization).
- [x] Pagination and rate limit tests pass (clamping, Redis URL parsing).
- [x] `.env.example` contains no real secrets (placeholder URLs only).
- [x] Security-sensitive configuration is documented (Redis auth, CORS, SSRF).
