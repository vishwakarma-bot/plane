# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class AssignmentType(models.TextChoices):
    QA = "qa", "QA"
    DEVELOPMENT = "development", "Development"
    REVIEW = "review", "Review"
    RESEARCH = "research", "Research"


class AssignmentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class AgentAssignment(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="agent_%(class)ss")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="agent_%(class)ss")
    work_item = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="agent_assignments")
    agent_ref = models.CharField(max_length=255)
    assignment_type = models.CharField(max_length=50, choices=AssignmentType.choices)
    status = models.CharField(max_length=50, choices=AssignmentStatus.choices, default=AssignmentStatus.PENDING)

    class Meta:
        verbose_name = "Agent Assignment"
        verbose_name_plural = "Agent Assignments"
        db_table = "agent_infra_agent_assignments"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.agent_ref} -> {self.work_item_id}"
