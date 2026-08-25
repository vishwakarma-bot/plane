# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models
from django.utils import timezone

from plane.db.models.base import BaseModel


class BudgetPeriod(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"


class ModelRoutingConfig(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="model_routing_configs")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="model_routing_configs")
    model_ref = models.CharField(max_length=255)
    routing_priority = models.IntegerField(default=100)
    shadow_mode = models.BooleanField(default=False)
    budget_limit_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_period = models.CharField(
        max_length=10,
        choices=BudgetPeriod.choices,
        default=BudgetPeriod.MONTHLY,
    )
    budget_used_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    budget_period_started_at = models.DateTimeField(default=timezone.now)
    eligible_risk_classes = models.JSONField(default=list)
    eligible_assignment_types = models.JSONField(default=list)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "agent_infra_model_routing_config"
        unique_together = ("workspace", "project", "model_ref")
        ordering = ["routing_priority"]
