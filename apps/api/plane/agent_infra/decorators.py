# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import json
import logging
import time
from datetime import timedelta
from functools import wraps
from uuid import UUID

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder

from plane.agent_infra.models import IdempotencyRecord
from plane.agent_infra.models.idempotency import IdempotencyState
from plane.agent_infra.services.reconciliation import ReconciliationService

logger = logging.getLogger("plane.api")

CONFLICT_RETRY_ATTEMPTS = 3
CONFLICT_RETRY_DELAY_SECONDS = 0.5


def idempotent_callback(view_func):
    """Decorator for views that accept Development Center callbacks.

    Uses a state machine (in_progress → completed) to handle concurrent
    requests safely. Concurrent callers seeing an in_progress record will
    retry briefly rather than receiving a response with status 0.
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

        fingerprint_hash = _compute_fingerprint(request, **kwargs)
        now = timezone.now()
        expires_at = now + timedelta(hours=ReconciliationService.IDEMPOTENCY_RETENTION_HOURS)

        for attempt in range(CONFLICT_RETRY_ATTEMPTS):
            try:
                with transaction.atomic():
                    existing = (
                        IdempotencyRecord.objects.select_for_update()
                        .filter(idempotency_key=idempotency_key)
                        .first()
                    )
                    if existing:
                        if existing.expires_at <= now:
                            existing.delete()
                        elif existing.fingerprint_hash != fingerprint_hash:
                            return Response(
                                {
                                    "error_code": "IDEMPOTENCY_KEY_REUSED",
                                    "message": "Idempotency key was already used with a different request fingerprint.",
                                },
                                status=409,
                            )
                        elif existing.state == IdempotencyState.COMPLETED:
                            return _build_cached_response(existing)
                        elif existing.state == IdempotencyState.IN_PROGRESS:
                            if attempt < CONFLICT_RETRY_ATTEMPTS - 1:
                                time.sleep(CONFLICT_RETRY_DELAY_SECONDS)
                                continue
                            return Response(
                                {
                                    "error_code": "IDEMPOTENCY_IN_PROGRESS",
                                    "message": "Request is being processed. Retry later.",
                                    "retry_after": 1,
                                },
                                status=409,
                            )

                    IdempotencyRecord.objects.create(
                        idempotency_key=idempotency_key,
                        fingerprint_hash=fingerprint_hash,
                        state=IdempotencyState.IN_PROGRESS,
                        response_status=0,
                        response_body={},
                        expires_at=expires_at,
                    )
                break
            except IntegrityError:
                if attempt < CONFLICT_RETRY_ATTEMPTS - 1:
                    time.sleep(CONFLICT_RETRY_DELAY_SECONDS)
                    continue
                return Response(
                    {
                        "error_code": "IDEMPOTENCY_CONFLICT",
                        "message": "Concurrent idempotency key reservation. Retry later.",
                        "retry_after": 1,
                    },
                    status=409,
                )

        try:
            response = view_func(view_instance, request, *args, **kwargs)
        except Exception:
            IdempotencyRecord.objects.filter(
                idempotency_key=idempotency_key,
                fingerprint_hash=fingerprint_hash,
                state=IdempotencyState.IN_PROGRESS,
            ).delete()
            raise

        if response.status_code >= 500:
            IdempotencyRecord.objects.filter(
                idempotency_key=idempotency_key,
                fingerprint_hash=fingerprint_hash,
                state=IdempotencyState.IN_PROGRESS,
            ).delete()
            return response

        serialized_body = _serialize_response_body(response)
        IdempotencyRecord.objects.filter(
            idempotency_key=idempotency_key,
            fingerprint_hash=fingerprint_hash,
        ).update(
            state=IdempotencyState.COMPLETED,
            response_status=response.status_code,
            response_body=serialized_body,
            expires_at=expires_at,
        )
        if hasattr(response, "data"):
            response.data = serialized_body
        return response

    return wrapper


def _compute_fingerprint(request, **view_kwargs) -> str:
    slug = view_kwargs.get("slug", "")
    project_id = str(view_kwargs.get("project_id", ""))
    body_hash = hashlib.sha256(request.body or b"").hexdigest()
    canonical = f"{slug}:{project_id}:{request.path}:{request.method.upper()}:{body_hash}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
