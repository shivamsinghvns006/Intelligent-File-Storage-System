from importlib.util import find_spec
import unittest

from app.core.security_policy import (
    DEVELOPMENT_ORIGINS,
    resolve_allowed_origins,
    safe_configuration_error_fields,
)

SETTINGS_RUNTIME_AVAILABLE = find_spec("pydantic") is not None and find_spec(
    "pydantic_settings"
) is not None


class TestConfigurationValidation(unittest.TestCase):
    def test_missing_development_origins_use_local_allowlist(self) -> None:
        self.assertEqual(
            resolve_allowed_origins("development", None, True),
            DEVELOPMENT_ORIGINS,
        )

    def test_missing_production_origins_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "CORS_ALLOWED_ORIGINS is required"):
            resolve_allowed_origins("production", None, True)

    def test_empty_production_origins_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "CORS_ALLOWED_ORIGINS is required"):
            resolve_allowed_origins("production", "  ", True)

    def test_invalid_production_origins_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Wildcard"):
            resolve_allowed_origins("production", "*", True)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            resolve_allowed_origins("production", "http://app.example.test", True)

    def test_startup_error_format_contains_field_names_only(self) -> None:
        safe_message = safe_configuration_error_fields(
            [("cors_allowed_origins",), ("app_env",)]
        )
        self.assertEqual(safe_message, "app_env, cors_allowed_origins")
        self.assertNotIn("replace-with", safe_message)

    @unittest.skipUnless(
        SETTINGS_RUNTIME_AVAILABLE,
        "Pydantic Settings is not installed in this environment",
    )
    def test_settings_reject_missing_production_origins(self) -> None:
        from pydantic import ValidationError

        from app.core.config import Settings

        with self.assertRaises(ValidationError):
            Settings(_env_file=None, app_env="production")

    @unittest.skipUnless(
        SETTINGS_RUNTIME_AVAILABLE,
        "Pydantic Settings is not installed in this environment",
    )
    def test_formatted_settings_error_does_not_echo_rejected_value(self) -> None:
        from pydantic import ValidationError

        from app.core.config import Settings, configuration_error_fields

        marker = "must-not-appear-in-startup-output"
        with self.assertRaises(ValidationError) as raised:
            Settings(
                _env_file=None,
                cors_allowed_origins=f"https://user:{marker}@app.example.test",
            )

        message = configuration_error_fields(raised.exception)
        self.assertIn("cors_allowed_origins", message)
        self.assertNotIn(marker, message)


if __name__ == "__main__":
    unittest.main()
