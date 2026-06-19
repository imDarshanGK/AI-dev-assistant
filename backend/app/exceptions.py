import logging
from enum import Enum

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("ai_assistant.exceptions")


class ErrorCode(str, Enum):
    INVALID_TOKEN = "invalid_token"
    AUTHENTICATION_REQUIRED = "authentication_required"
    INVALID_CREDENTIALS = "invalid_credentials"
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    HISTORY_NOT_FOUND = "history_not_found"
    FAVORITE_NOT_FOUND = "favorite_not_found"
    SHARED_RESULT_NOT_FOUND = "shared_result_not_found"
    UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    RATE_LIMITED = "rate_limited"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    BAD_REQUEST = "bad_request"
    FORBIDDEN = "forbidden"
    ALREADY_SUBSCRIBED = "already_subscribed"
    SUBSCRIPTION_NOT_FOUND = "subscription_not_found"


class APIException(HTTPException):
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        detail: str,
        headers: dict | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


def map_http_exception_to_code(status_code: int, detail: str) -> str:
    detail_lower = detail.lower()

    # 401 Unauthorized
    if status_code == 401:
        if "authentication required" in detail_lower:
            return ErrorCode.AUTHENTICATION_REQUIRED
        if "invalid token" in detail_lower or "user not found" in detail_lower:
            return ErrorCode.INVALID_TOKEN
        if "invalid credentials" in detail_lower:
            return ErrorCode.INVALID_CREDENTIALS
        return "unauthorized"

    # 403 Forbidden
    if status_code == 403:
        if "invalid unsubscribe token" in detail_lower:
            return ErrorCode.INVALID_TOKEN
        return ErrorCode.FORBIDDEN

    # 404 Not Found
    if status_code == 404:
        if "history" in detail_lower:
            return ErrorCode.HISTORY_NOT_FOUND
        if "favorite" in detail_lower:
            return ErrorCode.FAVORITE_NOT_FOUND
        if "shared result" in detail_lower or "share" in detail_lower:
            return ErrorCode.SHARED_RESULT_NOT_FOUND
        if "subscription" in detail_lower:
            return ErrorCode.SUBSCRIPTION_NOT_FOUND
        return "not_found"

    # 409 Conflict
    if status_code == 409:
        if "already subscribed" in detail_lower:
            return ErrorCode.ALREADY_SUBSCRIBED
        if "email already exists" in detail_lower:
            return ErrorCode.EMAIL_ALREADY_EXISTS
        return "conflict"

    # 413 Content Too Large / Payload Too Large
    if status_code == 413:
        return ErrorCode.PAYLOAD_TOO_LARGE

    # 415 Unsupported Media Type
    if status_code == 415:
        return ErrorCode.UNSUPPORTED_FILE_TYPE

    # 429 Too Many Requests
    if status_code == 429:
        return ErrorCode.RATE_LIMITED

    # 400 Bad Request
    if status_code == 400:
        if "only .zip" in detail_lower:
            return ErrorCode.UNSUPPORTED_FILE_TYPE
        return ErrorCode.BAD_REQUEST

    # 500 Internal Server Error
    if status_code == 500:
        return ErrorCode.INTERNAL_SERVER_ERROR

    return (
        ErrorCode.BAD_REQUEST if status_code < 500 else ErrorCode.INTERNAL_SERVER_ERROR
    )


async def api_exception_handler(request: Request, exc: APIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "detail": exc.detail,
        },
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    error_code = map_http_exception_to_code(exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_code,
            "detail": exc.detail,
        },
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    details = []
    for err in errors:
        loc = " -> ".join(str(location_part) for location_part in err["loc"])
        details.append(f"{loc}: {err['msg']}")
    detail_str = "; ".join(details)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": ErrorCode.VALIDATION_ERROR,
            "detail": detail_str,
        },
    )
