# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class SourceType(models.TextChoices):
    PLANE = "plane", "Plane"
    REPOSITORY = "repository", "Repository"
    CI = "ci", "CI"
    INCIDENT = "incident", "Incident"
    EXTERNAL = "external", "External"


class AuthorityType(models.TextChoices):
    PRODUCT = "product", "Product"
    DESIGN = "design", "Design"
    ARCHITECTURE = "architecture", "Architecture"
    QA = "qa", "QA"
    SECURITY = "security", "Security"
    PLATFORM = "platform", "Platform"
    RELEASE = "release", "Release"


class Sensitivity(models.TextChoices):
    PUBLIC = "public", "Public"
    INTERNAL = "internal", "Internal"
    CONFIDENTIAL = "confidential", "Confidential"
    RESTRICTED = "restricted", "Restricted"


class KnowledgeSource(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="knowledge_sources")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="knowledge_sources")
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=50, choices=SourceType.choices)
    authority_type = models.CharField(max_length=50, choices=AuthorityType.choices)
    sensitivity = models.CharField(
        max_length=50,
        choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL,
    )
    url = models.URLField(blank=True)
    owner = models.ForeignKey(
        "db.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_knowledge_sources",
    )
    effective_from = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    retention_days = models.PositiveIntegerField(default=365)
    is_retired = models.BooleanField(default=False)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Knowledge Source"
        verbose_name_plural = "Knowledge Sources"
        db_table = "agent_infra_knowledge_sources"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "project"]),
            models.Index(fields=["source_type"]),
            models.Index(fields=["is_retired"]),
        ]

    def __str__(self):
        return self.name
