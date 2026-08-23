# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class IdempotencyState(models.TextChoices):
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"


class IdempotencyRecord(BaseModel):
    """Track processed idempotency keys to prevent duplicate processing."""

    idempotency_key = models.UUIDField(unique=True, db_index=True)
    fingerprint_hash = models.CharField(max_length=64, default="")
    state = models.CharField(
        max_length=20,
        choices=IdempotencyState.choices,
        default=IdempotencyState.IN_PROGRESS,
    )
    response_status = models.IntegerField(default=0)
    response_body = models.JSONField(default=dict)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Idempotency Record"
        verbose_name_plural = "Idempotency Records"
        db_table = "agent_infra_idempotency"
        indexes = [
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return str(self.idempotency_key)
