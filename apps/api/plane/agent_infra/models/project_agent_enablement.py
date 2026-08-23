# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.base import BaseModel


class AutonomyLevel(models.TextChoices):
    SUPERVISED = "supervised", "Supervised"
    SEMI_AUTONOMOUS = "semi_autonomous", "Semi-Autonomous"
    AUTONOMOUS = "autonomous", "Autonomous"


class ProjectAgentEnablement(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="agent_enablements")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="agent_enablements")
    agent_ref = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    max_autonomy_level = models.CharField(
        max_length=20,
        choices=AutonomyLevel.choices,
        default=AutonomyLevel.SUPERVISED,
    )
    allowed_assignment_types = models.JSONField(default=list)
    delegation_permissions = models.JSONField(default=list)
    enabled_by = models.ForeignKey(
        "db.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    enabled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_infra_project_agent_enablement"
        unique_together = ("workspace", "project", "agent_ref")
        indexes = [models.Index(fields=["workspace", "project"])]
