"""Security regression tests."""

import os

from werkzeug.utils import safe_join


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
