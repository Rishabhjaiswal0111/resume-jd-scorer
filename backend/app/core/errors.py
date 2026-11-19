"""One error shape for the whole API.

    {"error": {"code": "PDF_UNREADABLE", "message": "...", "request_id": "..."}}

Raise `AppError` (or a subclass) from services; handlers map it to HTTP.
Error codes are listed in docs/PLAN.md §11.4.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    code: str = "INTERNAL_ERROR"
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND


class ValidationFailedError(AppError):
    code = "VALIDATION_FAILED"
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT


class UnauthenticatedError(AppError):
    """No valid session (missing, expired or signed-out cookie)."""

    code = "UNAUTHENTICATED"
    http_status = status.HTTP_401_UNAUTHORIZED


class InvalidCredentialsError(AppError):
    code = "INVALID_CREDENTIALS"
    http_status = status.HTTP_401_UNAUTHORIZED


# ---- Domain errors (PLAN.md §11.4) ----


class PdfUnreadableError(AppError):
    code = "PDF_UNREADABLE"
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT


class PdfScannedError(AppError):
    code = "PDF_SCANNED"
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT


class PdfTooLargeError(AppError):
    code = "PDF_TOO_LARGE"
    http_status = status.HTTP_413_CONTENT_TOO_LARGE


class RubricEmptyError(AppError):
    code = "RUBRIC_EMPTY"
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT


class LLMError(AppError):
    """Base for LLM failures. `retryable` drives the client's backoff loop."""

    code = "LLM_PROVIDER_ERROR"
    http_status = status.HTTP_502_BAD_GATEWAY
    retryable = True


class LLMTimeoutError(LLMError):
    code = "LLM_TIMEOUT"
    http_status = status.HTTP_504_GATEWAY_TIMEOUT


class LLMRateLimitedError(LLMError):
    code = "LLM_RATE_LIMITED"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE


class LLMProviderError(LLMError):
    code = "LLM_PROVIDER_ERROR"


class LLMRequestRejectedError(LLMError):
    """4xx other than 429 (bad request, auth, no provider for params). Retrying won't help."""

    code = "LLM_REQUEST_REJECTED"
    retryable = False


class LLMRefusedError(LLMError):
    """The model declined the request (Claude `stop_reason: "refusal"`)."""

    code = "LLM_REFUSED"
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    retryable = False


class LLMInvalidOutputError(LLMError):
    code = "LLM_INVALID_OUTPUT"
    retryable = False
    # The raw model text, so a caller can send it back in a repair prompt.
    raw_text: str | None = None


class LLMResponsePendingError(LLMError):
    """manual provider: the prompt was written to disk and is waiting for an answer file."""

    code = "LLM_RESPONSE_PENDING"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    retryable = False


class LLMNotConfiguredError(LLMError):
    code = "LLM_NOT_CONFIGURED"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    retryable = False


class PriceMissingError(AppError):
    code = "PRICE_MISSING"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR


def _request_id(request: Request) -> str | None:
    value = request.scope.get("state", {}).get("request_id")
    return str(value) if value is not None else None


def error_body(
    request: Request, code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": _request_id(request),
    }
    if details:
        body["details"] = details
    return {"error": body}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        log.warning("app_error", code=exc.code, message=exc.message)
        return JSONResponse(
            error_body(request, exc.code, exc.message, exc.details), status_code=exc.http_status
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            error_body(
                request,
                "VALIDATION_FAILED",
                "Request validation failed",
                {"errors": exc.errors()},
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
        return JSONResponse(error_body(request, code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error")
        # Rendered outside RequestContextMiddleware, so add the request id header here.
        request_id = _request_id(request)
        return JSONResponse(
            error_body(request, "INTERNAL_ERROR", "Something went wrong"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"x-request-id": request_id} if request_id else None,
        )
