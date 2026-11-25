"""Pure validation for browser-origin configuration."""

from collections.abc import Iterable
from urllib.parse import urlsplit

DEVELOPMENT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def resolve_allowed_origins(
    app_env: str,
    raw_origins: str | None,
    allow_credentials: bool,
) -> tuple[str, ...]:
    """Apply environment defaults and require an explicit production allowlist."""
    if raw_origins is None or not raw_origins.strip():
        if app_env == "production":
            raise ValueError("CORS_ALLOWED_ORIGINS is required in production.")
        raw_origins = ",".join(DEVELOPMENT_ORIGINS)

    return validate_origins(app_env, raw_origins, allow_credentials)


def safe_configuration_error_fields(fields: Iterable[Iterable[object]]) -> str:
    """Format configuration field names only, never the rejected values."""
    names = sorted({".".join(str(part) for part in field) for field in fields})
    return ", ".join(names) or "configuration"


def validate_origins(
    app_env: str,
    raw_origins: str,
    allow_credentials: bool,
) -> tuple[str, ...]:
    """Validate and normalize an explicit, comma-separated origin allowlist."""
    origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
    if not origins:
        raise ValueError("CORS_ALLOWED_ORIGINS must contain at least one exact origin.")

    normalized: list[str] = []
    for origin in origins:
        if "*" in origin:
            raise ValueError("Wildcard browser origins are not allowed.")

        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CORS_ALLOWED_ORIGINS must contain exact HTTP(S) origins only.")

        if app_env == "production":
            if parsed.scheme != "https":
                raise ValueError("Production CORS origins must use HTTPS.")
            if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("Production CORS origins cannot use loopback hosts.")

        normalized.append(f"{parsed.scheme}://{parsed.netloc}")

    if len(set(normalized)) != len(normalized):
        raise ValueError("CORS_ALLOWED_ORIGINS cannot contain duplicate origins.")

    if allow_credentials and "*" in normalized:
        raise ValueError("Credentialed CORS requests require exact origins.")

    return tuple(normalized)
