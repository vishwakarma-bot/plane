# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.base import BaseModel


class EmergencyDeny(BaseModel):
    """Emergency kill switch that immediately denies all matching actions.

    Emergency denies override all other policies (priority 0). They can be
    activated in response to security incidents, critical failures, or
    suspicious activity. They are always workspace-scoped and affect all
    projects.
    """

    workspace = models.ForeignKey(
        "db.Workspace", on_delete=models.CASCADE, related_name="emergency_denies"
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="emergency_denies",
        help_text="Project scope. Null means workspace-wide (requires workspace admin).",
    )
    policy = models.ForeignKey(
        "agent_infra.AuthorizationPolicy",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="emergency_activations",
        help_text="The emergency policy that was activated (optional, can be ad-hoc)",
    )
    reason = models.TextField(help_text="Why this emergency deny was activated")
    activated_by = models.ForeignKey(
        "db.User", on_delete=models.SET_NULL, null=True, related_name="emergency_activations"
    )
    activated_at = models.DateTimeField(auto_now_add=True)
    scope_filter = models.JSONField(
        null=True, blank=True,
        help_text="Optional narrowing filter (subject_types, resource_types, actions). Null = deny all.",
    )
    is_active = models.BooleanField(default=True)
    deactivated_by = models.ForeignKey(
        "db.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="emergency_deactivations",
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.TextField(null=True, blank=True)
    incident_reference = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Link to incident tracking (e.g., work item ID, external ticket)"
    )

    class Meta:
        db_table = "agent_infra_emergency_denies"
        ordering = ("-activated_at",)
        indexes = [
            models.Index(fields=["workspace", "project", "is_active"], name="agent_infra_ed_ws_proj_active_idx"),
        ]

    def __str__(self):
        status = "ACTIVE" if self.is_active else "deactivated"
        return f"Emergency deny ({status}): {self.reason[:50]}"
