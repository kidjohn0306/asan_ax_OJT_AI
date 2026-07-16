import unittest

from config.features import (
    NORMALIZED_FEATURE_FLAGS,
    get_feature_flags,
    get_schema_mode,
    is_feature_enabled,
)


class FeatureFlagTests(unittest.TestCase):
    def test_default_schema_mode_is_legacy(self):
        self.assertEqual(get_schema_mode({}), "legacy")

    def test_allowed_schema_modes(self):
        for mode in ("legacy", "dual", "v2"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    get_schema_mode({"OJT_SHEETS_SCHEMA_MODE": mode}),
                    mode,
                )

    def test_invalid_schema_mode_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "OJT_SHEETS_SCHEMA_MODE"):
            get_schema_mode({"OJT_SHEETS_SCHEMA_MODE": "auto"})

    def test_all_normalized_features_default_off(self):
        flags = get_feature_flags({})
        self.assertEqual(set(flags), set(NORMALIZED_FEATURE_FLAGS))
        self.assertTrue(all(value is False for value in flags.values()))

    def test_only_literal_true_enables_feature(self):
        flag = "OJT_USE_NORMALIZED_MATERIALS"
        self.assertTrue(is_feature_enabled(flag, {flag: "true"}))
        self.assertFalse(is_feature_enabled(flag, {flag: "false"}))

    def test_invalid_boolean_fails_closed(self):
        flag = "OJT_USE_KNOWLEDGE_UNITS"
        with self.assertRaisesRegex(ValueError, flag):
            is_feature_enabled(flag, {flag: "yes"})

    def test_unknown_feature_flag_is_rejected(self):
        with self.assertRaises(KeyError):
            is_feature_enabled("OJT_UNKNOWN_FEATURE", {})


if __name__ == "__main__":
    unittest.main()
