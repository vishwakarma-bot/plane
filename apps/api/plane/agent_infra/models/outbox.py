# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class OutboxEventType(models.TextChoices):
    ASSIGNMENT_CREATED = "assignment_created", "Assignment Created"
    ASSIGNMENT_CANCELLED = "assignment_cancelled", "Assignment Cancelled"
    DISPOSITION_CREATED = "disposition_created", "Disposition Created"


class OutboxStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"


class AgentInfraOutbox(BaseModel):
    """Outbox pattern for reliable event delivery to Development Center."""

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="agent_infra_outbox_events",
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="agent_infra_outbox_events",
    )
    event_type = models.CharField(max_length=50, choices=OutboxEventType.choices)
    payload = models.JSONField()
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(
        max_length=50,
        choices=OutboxStatus.choices,
        default=OutboxStatus.PENDING,
    )
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Agent Infra Outbox Event"
        verbose_name_plural = "Agent Infra Outbox Events"
        db_table = "agent_infra_outbox"
        ordering = ("next_attempt_at",)
        indexes = [
            models.Index(fields=["status", "next_attempt_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.status})"
