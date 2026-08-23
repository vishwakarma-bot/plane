# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
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
        request.service_actor = None

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
        ).select_related("workspace").first()
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
        request_id = request.headers.get("X-Request-Id", "")
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = "\n".join([
            request.method.upper(),
            request.path.split("?")[0],
            body_hash,
            service_id,
            timestamp,
            request_id,
        ])
        expected = hmac.new(
            raw_secret.encode("utf-8"),
            canonical.encode("utf-8"),
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
        request.service_actor = identity.service_id
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.path.startswith("/api/v1/"):
            return None

        view_class = getattr(view_func, "cls", None) or getattr(view_func, "view_class", None)
        if view_class is None:
            return None

        required_permission = getattr(view_class, "requires_service_identity", None)
        if not required_permission or request.method.upper() != "POST":
            return None

        identity = getattr(request, "service_identity", None)
        if identity is None:
            return self._error_response(
                "SERVICE_IDENTITY_REQUIRED",
                "A valid service identity is required for this endpoint.",
                request,
                status=401,
            )

        workspace_slug = view_kwargs.get("slug")
        if workspace_slug and identity.workspace.slug != workspace_slug:
            return self._error_response(
                "PERMISSION_DENIED",
                "Service identity is not authorized for this workspace.",
                request,
                status=403,
            )

        permissions = identity.permissions or []
        if required_permission not in permissions:
            return self._error_response(
                "PERMISSION_DENIED",
                f"Service identity lacks required permission: {required_permission}",
                request,
                status=403,
            )

        request.service_actor = identity.service_id
        return None

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
