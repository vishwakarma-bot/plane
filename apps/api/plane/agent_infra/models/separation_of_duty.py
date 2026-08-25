# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.db import models

from plane.db.models.base import BaseModel


class ConstraintScope(models.TextChoices):
    RUN = "run", "Run"
    ASSIGNMENT = "assignment", "Assignment"
    PROJECT = "project", "Project"
    WORKSPACE = "workspace", "Workspace"


class SeparationOfDutyConstraint(BaseModel):
    """Separation-of-duty constraints that prevent conflicting role combinations.

    These enforce rules like:
    - An agent cannot verify its own output (no self-review)
    - The creator of an assignment cannot solely approve its disposition
    - A service identity cannot trigger and approve the same privileged action
    """

    workspace = models.ForeignKey(
        "db.Workspace", on_delete=models.CASCADE, related_name="sod_constraints"
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sod_constraints",
    )
    policy = models.ForeignKey(
        "agent_infra.AuthorizationPolicy",
        on_delete=models.CASCADE,
        related_name="sod_constraints",
        help_text="The policy that defines this constraint",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    conflicting_actions = models.JSONField(
        help_text="List of action names that cannot be performed by the same actor"
    )
    scope = models.CharField(max_length=20, choices=ConstraintScope.choices, default=ConstraintScope.RUN)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "agent_infra_sod_constraints"
        unique_together = ("workspace", "policy", "name")
        ordering = ["name"]

    def clean(self):
        super().clean()
        if not isinstance(self.conflicting_actions, list):
            raise ValidationError("conflicting_actions must be a list")
        if len(self.conflicting_actions) < 2:
            raise ValidationError("conflicting_actions must contain at least 2 actions")

    def __str__(self):
        return f"{self.name} ({self.scope})"
