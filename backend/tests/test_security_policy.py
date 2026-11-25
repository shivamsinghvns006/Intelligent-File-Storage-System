import unittest

from app.core.security_policy import DEVELOPMENT_ORIGINS, validate_origins


class TestCorsOriginPolicy(unittest.TestCase):
    def test_development_defaults_are_exact_origins(self) -> None:
        actual = validate_origins("development", ",".join(DEVELOPMENT_ORIGINS), True)
        self.assertEqual(actual, DEVELOPMENT_ORIGINS)

    def test_wildcard_is_rejected_with_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "Wildcard"):
            validate_origins("development", "*", True)

    def test_origin_paths_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, r"exact HTTP\(S\) origins"):
            validate_origins("development", "http://localhost:5173/app", False)

    def test_production_requires_https_and_non_loopback_hosts(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_origins("production", "http://app.example.test", True)
        with self.assertRaisesRegex(ValueError, "loopback"):
            validate_origins("production", "https://localhost", True)

    def test_empty_and_duplicate_origin_lists_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            validate_origins("development", " , ", True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_origins(
                "development",
                "http://localhost:5173,http://localhost:5173/",
                True,
            )


if __name__ == "__main__":
    unittest.main()
