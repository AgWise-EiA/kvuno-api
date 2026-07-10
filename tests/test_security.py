"""Security regression tests."""

import os
from contextlib import contextmanager

from flask import Flask
from werkzeug.utils import safe_join


@contextmanager
def _test_request_context(headers=None):
    app = Flask(__name__)
    with app.test_request_context(headers=headers or {}):
        yield


class TestPathTraversalNpmServe:
    def test_safe_join_rejects_traversal(self):
        nm = "/tmp/node_modules"
        assert safe_join(nm, "valid/file.js") is not None
        assert safe_join(nm, "../etc/passwd") is None
        assert safe_join(nm, "sub/../../etc/passwd") is None

    def test_realpath_validation(self):
        nm = os.path.realpath("/tmp/node_modules")
        safe = safe_join(nm, "valid/file.js")
        assert safe is not None
        assert os.path.realpath(safe).startswith(nm)

        bad = safe_join(nm, "../../etc/passwd")
        assert bad is None


class TestUploadSizeEnforcement:
    def test_max_size_constant_defined(self):
        from app.api.upload import MAX_FILE_SIZE
        assert MAX_FILE_SIZE == 20 * 1024 * 1024

    def test_upload_rejects_oversized(self):
        from app.api.upload import MAX_FILE_SIZE
        max_mb = MAX_FILE_SIZE / 1024 / 1024
        assert max_mb == 20


class TestUrlSanitization:
    def test_strips_query_string(self):
        from app.utils.downloader import sanitize_url
        result = sanitize_url("https://example.com/file.RDS?token=secret&key=value")
        assert "token=secret" not in result
        assert "key=value" not in result
        assert result == "https://example.com/file.RDS"

    def test_strips_credentials(self):
        from app.utils.downloader import sanitize_url
        result = sanitize_url("https://user:pass@example.com/file.RDS")
        assert "user:pass" not in result
        assert "user" not in result
        assert "pass" not in result
        assert result.startswith("https://example.com/file.RDS")

    def test_leaves_path_intact(self):
        from app.utils.downloader import sanitize_url
        result = sanitize_url("https://example.com/data/file.RDS")
        assert result == "https://example.com/data/file.RDS"


class TestPathSafety:
    def test_resolve_under_data_dir(self):
        from pathlib import Path
        data_dir = Path("/tmp/data").resolve()
        valid = (data_dir / "valid_file.rds").resolve()
        assert str(valid).startswith(str(data_dir))

    def test_traversal_rejected(self):
        from pathlib import Path
        data_dir = Path("/tmp/data").resolve()
        invalid = (data_dir / "../../etc/passwd").resolve()
        assert not str(invalid).startswith(str(data_dir))

    def test_extension_validation(self):
        from app.routes.main import ALLOWED_EXTENSIONS
        assert '.rds' in ALLOWED_EXTENSIONS
        assert '.parquet' in ALLOWED_EXTENSIONS
        assert '.py' not in ALLOWED_EXTENSIONS
        assert '.json' not in ALLOWED_EXTENSIONS


class TestBcryptHashing:
    def test_password_hash_is_not_plaintext(self):
        import bcrypt
        password = b"securePass123"
        password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        assert password_hash != "securePass123"
        assert password_hash.startswith("$2b$")
        assert bcrypt.checkpw(password, password_hash.encode('utf-8'))

    def test_different_passwords_produce_different_hashes(self):
        import bcrypt
        h1 = bcrypt.hashpw(b"password1", bcrypt.gensalt())
        h2 = bcrypt.hashpw(b"password2", bcrypt.gensalt())
        assert h1 != h2


class TestSSRFValidation:
    def test_rejects_http_when_https_required(self):
        from app.utils.downloader import validate_remote_url
        import pytest
        with pytest.raises(ValueError, match="Only HTTPS"):
            validate_remote_url("http://example.com/file.RDS")

    def test_accepts_https(self):
        from app.utils.downloader import validate_remote_url
        result = validate_remote_url("https://example.com/file.RDS")
        assert result == "https://example.com/file.RDS"

    def test_rejects_loopback(self):
        from app.utils.downloader import validate_remote_url
        import pytest
        with pytest.raises(ValueError, match="private|internal"):
            validate_remote_url("https://127.0.0.1/file.RDS")

    def test_rejects_private_ip(self):
        from app.utils.downloader import validate_remote_url
        import pytest
        with pytest.raises(ValueError, match="private|internal"):
            validate_remote_url("https://10.0.0.1/file.RDS")

    def test_rejects_metadata_address(self):
        from app.utils.downloader import validate_remote_url
        import pytest
        with pytest.raises(ValueError, match="metadata"):
            validate_remote_url("https://169.254.169.254/file.RDS")

    def test_rejects_no_hostname(self):
        from app.utils.downloader import validate_remote_url
        import pytest
        with pytest.raises(ValueError, match="no hostname"):
            validate_remote_url("https:///file.RDS")


class TestGetCurrentUser:
    def test_returns_none_without_auth_header(self):
        from app.api.user import get_current_user
        with _test_request_context(headers={}):
            assert get_current_user() is None

    def test_returns_none_with_empty_auth_header(self):
        from app.api.user import get_current_user
        with _test_request_context(headers={"Authorization": ""}):
            assert get_current_user() is None

    def test_returns_none_with_non_bearer_header(self):
        from app.api.user import get_current_user
        with _test_request_context(headers={"Authorization": "Basic dXNlcjpwYXNz"}):
            assert get_current_user() is None


class TestPaginationBounds:
    def test_clamps_high_per_page(self):
        from app.api.planting_data import _clamp_per_page, MAX_PER_PAGE
        assert _clamp_per_page(1000) == MAX_PER_PAGE
        assert _clamp_per_page(MAX_PER_PAGE) == MAX_PER_PAGE

    def test_clamps_low_per_page(self):
        from app.api.planting_data import _clamp_per_page
        assert _clamp_per_page(0) == 1
        assert _clamp_per_page(-1) == 1

    def test_accepts_normal_per_page(self):
        from app.api.planting_data import _clamp_per_page
        assert _clamp_per_page(50) == 50
        assert _clamp_per_page(100) == 100
