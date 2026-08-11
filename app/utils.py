"""Response envelope helpers and shared API error type.

All endpoints should return one of the following shapes:

Success (single resource):
    {
        "success": true,
        "message": "...",
        "data": { ... },
        "total": null
    }

Success (list):
    {
        "success": true,
        "message": "OK",
        "data": [ ... ],
        "total": 42
    }

Success (delete):
    {
        "success": true,
        "message": "Project deleted successfully",
        "data": { "id": 1 },
        "total": null
    }

Error:
    {
        "success": false,
        "message": "Project not found",
        "error": { "code": "NOT_FOUND", "details": null }
    }
"""

from typing import Any, Optional

from fastapi import HTTPException


class APIError(HTTPException):
    """HTTPException that also carries a machine-readable error code."""

    def __init__(
        self,
        status_code: int,
        message: str,
        code: str,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.message = message
        self.code = code
        self.details = details


# Canonical error codes used across the API. Keep values upper-snake-case.
NOT_FOUND = "NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"
CONFLICT = "CONFLICT"


def success_response(
    data: Any = None,
    message: str = "OK",
    total: Optional[int] = None,
) -> dict:
    """Build a uniform success envelope."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "total": total,
    }


def error_response(
    message: str,
    code: str,
    details: Optional[Any] = None,
) -> dict:
    """Build a uniform error envelope."""
    return {
        "success": False,
        "message": message,
        "error": {
            "code": code,
            "details": details,
        },
    }
