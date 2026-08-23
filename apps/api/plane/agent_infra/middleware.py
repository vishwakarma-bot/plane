# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hmac
import logging
from datetime import datetime, timedelta, timezone

from django.http import JsonResponse
from django.utils import timezone as django_timezone

from plane.agent_infra.models import ServiceIdentity

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Signature"
SERVICE_ID_HEADER = "X-Service-Id"
TIMESTAMP_HEADER = "X-Timestamp"
MAX_TIMESTAMP_SKEW_SECONDS = 300


class ServiceIdentityMiddleware:
    """
    Verify HMAC-SHA256 signatures from registered service identities.

    Extracts X-Service-Id, X-Signature, and X-Timestamp headers, verifies
    HMAC-SHA256(signing_secret, request_body + timestamp), and sets
    request.service_identity when valid.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.service_identity = None

        if not request.path.startswith("/api/v1/"):
            return self.get_response(request)

        service_id = request.headers.get(SERVICE_ID_HEADER)
        if not service_id:
            return self.get_response(request)

        signature = request.headers.get(SIGNATURE_HEADER)
        timestamp = request.headers.get(TIMESTAMP_HEADER)

        if not signature or not timestamp:
            return self._error_response(
                "SERVICE_IDENTITY_REQUIRED",
                "X-Signature and X-Timestamp headers are required when X-Service-Id is present.",
                request,
                status=401,
            )

        if not self._is_timestamp_valid(timestamp):
            return self._error_response(
                "TIMESTAMP_EXPIRED",
                "Request timestamp is outside the allowed window.",
                request,
                status=401,
            )

        identity = ServiceIdentity.objects.filter(
            service_id=service_id,
            is_active=True,
        ).first()
        if identity is None:
            return self._error_response(
                "SERVICE_IDENTITY_INVALID",
                f"Unknown or inactive service identity: {service_id}",
                request,
                status=401,
            )

        raw_secret = identity.get_raw_signing_secret()
        if not raw_secret:
            return self._error_response(
                "SERVICE_IDENTITY_INVALID",
                "Service identity signing secret is not configured.",
                request,
                status=401,
            )

        body = request.body or b""
        expected = hmac.new(
            raw_secret.encode("utf-8"),
            body + timestamp.encode("utf-8"),
            digestmod="sha256",
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return self._error_response(
                "SIGNATURE_INVALID",
                "HMAC signature verification failed.",
                request,
                status=401,
            )

        identity.last_seen_at = django_timezone.now()
        identity.save(update_fields=["last_seen_at", "updated_at"])

        request.service_identity = identity
        return self.get_response(request)

    def _is_timestamp_valid(self, timestamp: str) -> bool:
        try:
            if timestamp.endswith("Z"):
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                parsed = datetime.fromisoformat(timestamp)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return False

        now = django_timezone.now()
        delta = abs(now - parsed)
        return delta <= timedelta(seconds=MAX_TIMESTAMP_SKEW_SECONDS)

    def _error_response(self, error_code: str, message: str, request, status: int):
        correlation_id = request.headers.get("X-Request-Id", "")
        return JsonResponse(
            {
                "error_code": error_code,
                "message": message,
                "correlation_id": correlation_id,
                "retry_after": None,
            },
            status=status,
        )
