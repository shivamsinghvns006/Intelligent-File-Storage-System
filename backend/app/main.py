"""Minimal FastAPI application shell; product routes belong to later milestones."""

import logging
import sys
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import configuration_error_fields, get_settings
from app.core.logging import configure_logging

logger = logging.getLogger("ifss.api")

try:
    settings = get_settings()
except ValidationError as error:
    fields = configuration_error_fields(error)
    sys.stderr.write(f"IFSS startup failed: invalid configuration for {fields}.\n")
    raise SystemExit(2) from None
except Exception as error:
    sys.stderr.write(
        "IFSS startup failed while loading configuration "
        f"(error type: {type(error).__name__}).\n"
    )
    raise SystemExit(2) from None

configure_logging(settings.log_level)

api = FastAPI(
    title="IFSS API",
    version="0.1.0",
    debug=False,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-CSRF-Token",
        "Idempotency-Key",
        "X-Request-ID",
        "Range",
        "Content-Range",
        "Digest",
    ],
    expose_headers=[
        "Content-Disposition",
        "ETag",
        "X-Request-ID",
        "Accept-Ranges",
        "Content-Range",
    ],
)


@api.middleware("http")
async def add_request_security_headers(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception as error:
        logger.error(
            "request_failed request_id=%s error_type=%s",
            request_id,
            type(error).__name__,
        )
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id,
                }
            },
        )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@api.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, _error: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "request_id": request_id,
            }
        },
    )


@api.get("/health", include_in_schema=False)
async def process_health() -> dict[str, str]:
    """Report that the API process can serve requests; this is not readiness."""
    return {"status": "ok"}


app = api
