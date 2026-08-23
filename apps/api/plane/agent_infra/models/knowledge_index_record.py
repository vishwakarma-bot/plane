# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models import BaseModel


class IndexAction(models.TextChoices):
    INDEX = "index", "Index"
    REINDEX = "reindex", "Reindex"
    DELETE = "delete", "Delete"


class IndexRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class KnowledgeIndexRecord(BaseModel):
    """Tracks the reconciliation state between Plane knowledge and
    downstream index/vector stores in Development Center.

    Each record represents a request to index, reindex, or delete
    knowledge content in the external system, with observed-state tracking.
    """

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="knowledge_index_records",
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="knowledge_index_records",
    )
    knowledge_version = models.ForeignKey(
        "agent_infra.KnowledgeVersion",
        on_delete=models.CASCADE,
        related_name="index_records",
    )
    action = models.CharField(
        max_length=20,
        choices=IndexAction.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=IndexRequestStatus.choices,
        default=IndexRequestStatus.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    external_ref = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Reference ID in the downstream index/vector store",
    )
    last_observed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time the index state was verified",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the action has been verified in the downstream system",
    )

    class Meta:
        db_table = "agent_infra_knowledge_index_records"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(
                fields=["workspace", "project", "status"],
                name="idx_kir_ws_proj_status",
            ),
            models.Index(
                fields=["knowledge_version", "action"],
                name="idx_kir_version_action",
            ),
        ]

    def __str__(self):
        return f"IndexRecord({self.action}/{self.status}) for version {self.knowledge_version_id}"
