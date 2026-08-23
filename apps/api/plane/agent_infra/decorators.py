# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
from datetime import timedelta
from functools import wraps
from uuid import UUID

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder

from plane.agent_infra.models import IdempotencyRecord
from plane.agent_infra.services.reconciliation import ReconciliationService

logger = logging.getLogger("plane.api")


def idempotent_callback(view_func):
    """Decorator for views that accept Development Center callbacks.

    Checks X-Idempotency-Key header. If the key was already processed,
    returns the cached response. Otherwise, processes and caches.
    """

    @wraps(view_func)
    def wrapper(view_instance, request, *args, **kwargs):
        raw_key = request.headers.get("X-Idempotency-Key") or request.META.get("HTTP_X_IDEMPOTENCY_KEY")
        if not raw_key:
            return view_func(view_instance, request, *args, **kwargs)

        try:
            idempotency_key = UUID(str(raw_key))
        except (TypeError, ValueError):
            return Response(
                {
                    "error_code": "INVALID_IDEMPOTENCY_KEY",
                    "message": "X-Idempotency-Key must be a valid UUID.",
                },
                status=400,
            )

        now = timezone.now()
        existing = IdempotencyRecord.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.expires_at <= now:
                existing.delete()
            else:
                return _build_cached_response(existing)

        response = view_func(view_instance, request, *args, **kwargs)
        if response.status_code >= 500:
            return response

        expires_at = now + timedelta(hours=ReconciliationService.IDEMPOTENCY_RETENTION_HOURS)
        serialized_body = _serialize_response_body(response)
        IdempotencyRecord.objects.update_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "response_status": response.status_code,
                "response_body": serialized_body,
                "expires_at": expires_at,
            },
        )
        if hasattr(response, "data"):
            response.data = serialized_body
        return response

    return wrapper


def _serialize_response_body(response):
    if hasattr(response, "data"):
        return json.loads(json.dumps(response.data, cls=JSONEncoder))
    if isinstance(response, HttpResponse):
        content_type = response.get("Content-Type", "")
        if "json" in content_type:
            try:
                return json.loads(response.content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {"raw": response.content.decode("utf-8", errors="replace")}
        return {"raw": response.content.decode("utf-8", errors="replace")}
    return {}


def _build_cached_response(record: IdempotencyRecord):
    try:
        from rest_framework.response import Response as DRFResponse

        return DRFResponse(record.response_body, status=record.response_status)
    except Exception:
        return HttpResponse(
            json.dumps(record.response_body),
            status=record.response_status,
            content_type="application/json",
        )
