# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.base import BaseModel


class IntegrationType(models.TextChoices):
    MCP = "mcp", "MCP"
    A2A = "a2a", "A2A"
    GIT_CI = "git_ci", "Git/CI"
    DEPLOYMENT = "deployment", "Deployment"


class HealthStatus(models.TextChoices):
    HEALTHY = "healthy", "Healthy"
    DEGRADED = "degraded", "Degraded"
    UNREACHABLE = "unreachable", "Unreachable"
    UNKNOWN = "unknown", "Unknown"


class RegistrationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    DEGRADED = "degraded", "Degraded"
    RETIRED = "retired", "Retired"


class ApprovalClass(models.TextChoices):
    AUTO = "auto", "Auto"
    MANUAL = "manual", "Manual"
    RESTRICTED = "restricted", "Restricted"


class IntegrationRegistration(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="integration_registrations")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="integration_registrations")
    integration_ref = models.CharField(max_length=255)
    integration_type = models.CharField(max_length=20, choices=IntegrationType.choices)
    server_identity = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.ACTIVE,
    )
    health_status = models.CharField(
        max_length=20,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
    )
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    granted_agents = models.JSONField(default=list)
    granted_scopes = models.JSONField(default=list)
    approval_class = models.CharField(
        max_length=20,
        choices=ApprovalClass.choices,
        default=ApprovalClass.AUTO,
    )
    failure_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = "agent_infra_integration_registration"
        unique_together = ("workspace", "project", "integration_ref")
