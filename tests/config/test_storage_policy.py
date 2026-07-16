import os
import unittest
from unittest.mock import patch

from config.storage import is_strict_sheets_storage, should_fallback_to_local


class StoragePolicyTests(unittest.TestCase):
    def test_strict_true_disables_local_fallback(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "true"}, clear=False):
            self.assertTrue(is_strict_sheets_storage())
            self.assertFalse(should_fallback_to_local())

    def test_strict_false_allows_local_fallback(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "false"}, clear=False):
            self.assertFalse(is_strict_sheets_storage())
            self.assertTrue(should_fallback_to_local())

    def test_invalid_value_fails_closed(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "yes"}, clear=False):
            with self.assertRaisesRegex(ValueError, "OJT_STRICT_SHEETS_STORAGE"):
                is_strict_sheets_storage()


if __name__ == "__main__":
    unittest.main()
