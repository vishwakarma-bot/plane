# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

from rest_framework.response import Response

# Standard agent_infra protocol error codes
INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
SERVICE_IDENTITY_REQUIRED = "SERVICE_IDENTITY_REQUIRED"
KNOWLEDGE_CONTEXT_INVALID = "KNOWLEDGE_CONTEXT_INVALID"
AUTHORITY_REVIEWER_REQUIRED = "AUTHORITY_REVIEWER_REQUIRED"


def agent_infra_error_response(
    error_code: str,
    message: str,
    status: int,
    correlation_id: str = None,
    extra: dict = None,
) -> Response:
    """Build a standard agent_infra protocol error response."""
    payload = {
        "error_code": error_code,
        "message": message,
        "correlation_id": correlation_id or "",
        "retry_after": None,
    }
    if extra:
        payload.update(extra)
    return Response(payload, status=status)


def format_validation_errors(errors) -> str:
    """Serialize DRF validation errors into a single message string."""
    if isinstance(errors, dict):
        return json.dumps(errors)
    return str(errors)


def agent_infra_validation_error_response(errors, request, status: int = 400) -> Response:
    """Return a protocol-formatted validation error response."""
    correlation_id = request.headers.get("X-Request-Id")
    return agent_infra_error_response(
        VALIDATION_ERROR,
        format_validation_errors(errors),
        status,
        correlation_id=correlation_id,
    )
