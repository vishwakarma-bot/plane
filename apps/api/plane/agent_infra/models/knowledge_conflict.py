# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models import BaseModel


class ConflictStatus(models.TextChoices):
    OPEN = "open", "Open"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    RESOLVED = "resolved", "Resolved"
    SUPERSEDED = "superseded", "Superseded"


class ConflictType(models.TextChoices):
    AUTHORITY = "authority", "Authority Conflict (multiple approved versions)"
    SEMANTIC = "semantic", "Semantic Conflict (contradictory content across sources)"
    STALENESS = "staleness", "Staleness Conflict (expired source still referenced)"


class KnowledgeConflict(BaseModel):
    """Tracks conflicts between knowledge versions, including
    cross-source semantic conflicts and single-source authority conflicts.

    Each conflict records the involved versions, the type of conflict,
    its resolution status, and the human decision that resolves it.
    """

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="knowledge_conflicts",
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="knowledge_conflicts",
    )
    version_a = models.ForeignKey(
        "agent_infra.KnowledgeVersion",
        on_delete=models.CASCADE,
        related_name="conflicts_as_a",
    )
    version_b = models.ForeignKey(
        "agent_infra.KnowledgeVersion",
        on_delete=models.CASCADE,
        related_name="conflicts_as_b",
    )
    conflict_type = models.CharField(
        max_length=20,
        choices=ConflictType.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=ConflictStatus.choices,
        default=ConflictStatus.OPEN,
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Auto-generated or human-provided conflict description",
    )
    resolution_summary = models.TextField(
        blank=True,
        default="",
        help_text="How the conflict was resolved",
    )
    resolved_by = models.ForeignKey(
        "db.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_knowledge_conflicts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    winning_version = models.ForeignKey(
        "agent_infra.KnowledgeVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conflict_wins",
        help_text="The version that prevails after resolution",
    )
    blocks_execution = models.BooleanField(
        default=True,
        help_text="Whether this conflict blocks assignment execution",
    )

    class Meta:
        db_table = "agent_infra_knowledge_conflicts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["workspace", "project", "status"],
                name="idx_kc_ws_proj_status",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(version_a=models.F("version_b")),
                name="conflict_versions_differ",
            ),
        ]

    def __str__(self):
        return f"Conflict({self.conflict_type}/{self.status}): v{self.version_a_id} vs v{self.version_b_id}"
