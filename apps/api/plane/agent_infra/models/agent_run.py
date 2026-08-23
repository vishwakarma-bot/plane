# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class RunOutcome(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"
    PARTIAL = "partial", "Partial"
    BLOCKED = "blocked", "Blocked"


class AgentRun(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="agent_%(class)ss")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="agent_%(class)ss")
    assignment = models.ForeignKey(
        "agent_infra.AgentAssignment",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    agent_ref = models.CharField(max_length=255)
    model_used = models.CharField(max_length=255)
    outcome = models.CharField(max_length=50, choices=RunOutcome.choices)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    correlation_id = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Agent Run"
        verbose_name_plural = "Agent Runs"
        db_table = "agent_infra_agent_runs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.agent_ref} ({self.outcome})"
