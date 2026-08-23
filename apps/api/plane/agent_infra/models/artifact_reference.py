# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class ArtifactType(models.TextChoices):
    SCREENSHOT = "screenshot", "Screenshot"
    LOG = "log", "Log"
    DIFF = "diff", "Diff"
    REPORT = "report", "Report"
    TRACE = "trace", "Trace"


class ArtifactClassification(models.TextChoices):
    PUBLIC = "public", "Public"
    INTERNAL = "internal", "Internal"
    SENSITIVE = "sensitive", "Sensitive"


class ArtifactReference(BaseModel):
    run = models.ForeignKey(
        "agent_infra.AgentRun",
        on_delete=models.CASCADE,
        related_name="artifact_references",
    )
    artifact_type = models.CharField(max_length=50, choices=ArtifactType.choices)
    storage_ref = models.CharField(max_length=2048)
    hash = models.CharField(max_length=255)
    classification = models.CharField(max_length=50, choices=ArtifactClassification.choices)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Artifact Reference"
        verbose_name_plural = "Artifact References"
        db_table = "agent_infra_artifact_references"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.artifact_type} for run {self.run_id}"
