"""Uniform API error envelope: {"error": {"code", "message", "details"}}. Never fail silently."""

import logging

from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return None  # Django returns 500; logged above
    data = response.data
    has_detail = isinstance(data, dict) and "detail" in data
    response.data = {
        "error": {
            "code": getattr(exc, "default_code", "error"),
            "message": str(data["detail"]) if has_detail else "Request failed",
            "details": None if has_detail else data,
        }
    }
    return response
