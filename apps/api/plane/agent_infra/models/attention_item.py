# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class AgentInfraAttentionItem(BaseModel):
    """Operator-visible drift item created during reconciliation."""

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="agent_infra_attention_items",
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="agent_infra_attention_items",
    )
    entity_type = models.CharField(max_length=50)
    entity_id = models.UUIDField()
    drift_type = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Agent Infra Attention Item"
        verbose_name_plural = "Agent Infra Attention Items"
        db_table = "agent_infra_attention_items"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "project", "resolved_at"]),
            models.Index(fields=["entity_type", "entity_id", "drift_type"]),
        ]

    def __str__(self):
        return f"{self.drift_type} ({self.entity_type}:{self.entity_id})"
