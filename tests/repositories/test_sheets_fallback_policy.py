import os
import unittest
from unittest.mock import patch

from repositories.sheets_repo import _fallback_on_error


class FakeLocal:
    def read(self):
        return "local"


class FakeSheets:
    _local_fallback = None

    @_fallback_on_error(FakeLocal)
    def read(self):
        raise RuntimeError("sheets unavailable")


class SheetsFallbackPolicyTests(unittest.TestCase):
    def test_strict_mode_reraises_sheets_error(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "true"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "sheets unavailable"):
                FakeSheets().read()

    def test_non_strict_mode_uses_local_fallback(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "false"}, clear=False):
            self.assertEqual(FakeSheets().read(), "local")


if __name__ == "__main__":
    unittest.main()
