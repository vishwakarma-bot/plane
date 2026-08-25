# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.base import BaseModel


class CompatibilityEntityType(models.TextChoices):
    AGENT = "agent", "Agent"
    SKILL = "skill", "Skill"
    MODEL = "model", "Model"
    ENVIRONMENT = "environment", "Environment"


class CompatibilityRecord(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="compatibility_records")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="compatibility_records")
    source_type = models.CharField(max_length=20, choices=CompatibilityEntityType.choices)
    source_ref = models.CharField(max_length=255)
    target_type = models.CharField(max_length=20, choices=CompatibilityEntityType.choices)
    target_ref = models.CharField(max_length=255)
    compatible = models.BooleanField()
    reason = models.TextField(blank=True, default="")
    last_checked_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_infra_compatibility_record"
        unique_together = ("workspace", "project", "source_type", "source_ref", "target_type", "target_ref")
