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
