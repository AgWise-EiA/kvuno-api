# Security Implementation Task List

This task list is derived from `docs/SECURITY.md` and is intended to guide remediation work before implementation begins.

## Immediate

- [ ] Replace placeholder authentication in `app/api/user.py` and `app/dto/auth.py`.
  - [ ] Add persistent user storage or connect to the existing user model if available.
  - [ ] Hash passwords with `bcrypt` or `argon2`.
  - [ ] Validate credentials during login.
  - [ ] Return a real session or token after successful login.
  - [ ] Add authentication tests for register, login, invalid credentials, and duplicate users.

- [ ] Enforce authentication on protected endpoints.
  - [ ] Protect upload endpoints in `app/api/upload.py`.
  - [ ] Protect planting data endpoints in `app/api/planting_data.py`.
  - [ ] Protect relevant UI processing and progress routes in `app/routes/main.py`.
  - [ ] Ensure OpenAPI security declarations match actual endpoint behavior.

- [ ] Fix path traversal in `/npm/<path>` in `app/routes/main.py`.
  - [ ] Validate resolved paths with `safe_join` or equivalent.
  - [ ] Reject requests that resolve outside `node_modules`.
  - [ ] Consider disabling this route outside development.
  - [ ] Add traversal regression tests.

- [ ] Remove the real token from `.env.example`.
  - [ ] Replace the `REMOTE_RDS_URLS` value with a placeholder URL.
  - [ ] Review adjacent example values for secrets or internal credentials.

- [ ] Add server-side upload size enforcement in `app/api/upload.py`.
  - [ ] Enforce `MAX_FILE_SIZE_MB` on the server.
  - [ ] Return HTTP `413` for oversized requests.
  - [ ] Keep client-side limits as hints only.
  - [ ] Add upload size tests.

## Short-Term

- [ ] Restrict CORS in `app/__init__.py`.
  - [ ] Configure allowed origins from environment.
  - [ ] Avoid default allow-all behavior.
  - [ ] Decide whether credentialed cross-origin requests are needed.

- [ ] Validate paths in `/ui/progress/<file_name>` in `app/routes/main.py`.
  - [ ] Resolve requested files under `DATA_DIR`.
  - [ ] Reject traversal attempts.
  - [ ] Return `404` for invalid or escaped paths.

- [ ] Validate `/ui/process` inputs in `app/routes/main.py`.
  - [ ] Ensure only expected files can be processed.
  - [ ] Reject path traversal and unexpected file extensions.
  - [ ] Add tests for invalid file names.

- [ ] Sanitize URL logging in `app/utils/downloader.py`.
  - [ ] Strip query strings before logging.
  - [ ] Strip embedded credentials before logging.
  - [ ] Add a unit test or helper-level test for sanitized output.

- [ ] Add rate limiting.
  - [ ] Rate limit authentication endpoints.
  - [ ] Rate limit upload endpoints.
  - [ ] Rate limit public data endpoints.
  - [ ] Prefer the existing Flask-Limiter dependency if present.

## Medium-Term

- [ ] Add SSRF protections to remote downloads in `app/services/housekeeper.py` and `app/utils/downloader.py`.
  - [ ] Require HTTPS URLs.
  - [ ] Add an allow-list of approved domains.
  - [ ] Disable redirects or validate redirect targets.
  - [ ] Reject private, loopback, link-local, and metadata service addresses.
  - [ ] Avoid logging sensitive URL components.

- [ ] Configure Redis authentication in `app/celery_app.py`.
  - [ ] Require authenticated Redis URLs in production.
  - [ ] Update `.env.example` with a password-based example.
  - [ ] Document local development behavior separately from production behavior.

- [ ] Add pagination bounds in `app/api/planting_data.py`.
  - [ ] Clamp `per_page` to a safe maximum, such as `500`.
  - [ ] Validate malformed pagination values.
  - [ ] Add tests for high, low, and invalid pagination inputs.

- [ ] Limit SSE clients in `app/routes/main.py`.
  - [ ] Add a maximum number of concurrent SSE connections.
  - [ ] Add cleanup for stale clients.
  - [ ] Add timeout behavior for clients that stop reading.

## Long-Term

- [ ] Disable automatic startup migrations in production in `app/__init__.py`.
  - [ ] Default production deployments to `RUN_MIGRATIONS=false`.
  - [ ] Move migrations to a separate deployment step.
  - [ ] Document operational migration procedure.

- [ ] Add security headers for UI responses.
  - [ ] Add Content Security Policy.
  - [ ] Add `X-Frame-Options` or `frame-ancestors`.
  - [ ] Add `Referrer-Policy`.
  - [ ] Add other headers appropriate to the deployment model.

- [ ] Add dependency vulnerability scanning to CI.
  - [ ] Add Python dependency scanning, such as `pip audit`.
  - [ ] Add JavaScript dependency scanning if frontend packages are used.
  - [ ] Decide whether audit failures should block merges.

- [ ] Consider API keys for programmatic access.
  - [ ] Define API key scope and rotation requirements.
  - [ ] Add storage for hashed API keys.
  - [ ] Add authentication middleware for machine clients.
  - [ ] Document API key issuance and revocation.

## Verification Checklist

- [ ] Authentication and authorization tests pass.
- [ ] Upload security tests pass.
- [ ] Path traversal regression tests pass.
- [ ] Downloader SSRF and logging tests pass.
- [ ] Pagination and rate limit tests pass.
- [ ] `.env.example` contains no real secrets.
- [ ] Security-sensitive configuration is documented for local and production use.
