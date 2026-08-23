# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.db import models

from plane.db.models.base import BaseModel


class PolicyScope(models.TextChoices):
    WORKSPACE = "workspace", "Workspace"
    PROJECT = "project", "Project"


class PolicyEffect(models.TextChoices):
    ALLOW = "allow", "Allow"
    DENY = "deny", "Deny"
    REQUIRE_APPROVAL = "require_approval", "Require Approval"


class PolicyStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    ACTIVE = "active", "Active"
    DEPRECATED = "deprecated", "Deprecated"
    REVOKED = "revoked", "Revoked"


class AutonomyClassification(models.TextChoices):
    UNATTENDED = "unattended", "Unattended"
    SUPERVISED = "supervised", "Supervised"
    ATTENDED = "attended", "Attended"


VALID_POLICY_TRANSITIONS = {
    "draft": {"pending_approval", "active"},
    "pending_approval": {"active", "draft"},
    "active": {"deprecated", "revoked"},
    "deprecated": {"active", "revoked"},
    "revoked": set(),
}


def validate_policy_status_transition(current_status, new_status):
    allowed = VALID_POLICY_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValidationError(
            f"Invalid policy status transition: {current_status} → {new_status}. "
            f"Allowed: {allowed or 'none (terminal state)'}"
        )


class AuthorizationPolicy(BaseModel):
    """Versioned authorization policy stored in Plane for governance.

    Policies define deterministic rules for what subjects may do to resources.
    They are evaluated by the policy engine — no AI/LLM in the decision path.
    """

    workspace = models.ForeignKey(
        "db.Workspace", on_delete=models.CASCADE, related_name="authorization_policies"
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="authorization_policies",
    )
    name = models.CharField(max_length=255, db_index=True)
    version = models.CharField(max_length=50, default="1.0.0")
    description = models.TextField()
    scope = models.CharField(max_length=20, choices=PolicyScope.choices, default=PolicyScope.PROJECT)
    priority = models.IntegerField(default=100)
    effect = models.CharField(max_length=20, choices=PolicyEffect.choices)
    subjects = models.JSONField(help_text="List of subject definitions")
    resources = models.JSONField(help_text="List of resource definitions")
    actions = models.JSONField(help_text="List of action definitions")
    conditions = models.JSONField(null=True, blank=True, help_text="Additional matching conditions")
    separation_of_duty = models.JSONField(
        null=True, blank=True, help_text="Separation-of-duty constraint rules"
    )
    autonomy_classification = models.CharField(
        max_length=20,
        choices=AutonomyClassification.choices,
        null=True,
        blank=True,
    )
    emergency = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=PolicyStatus.choices, default=PolicyStatus.DRAFT
    )
    content_hash = models.CharField(max_length=64)
    revision_number = models.PositiveIntegerField(default=1)
    previous_revision = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="next_revisions"
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    owner = models.CharField(max_length=255, null=True, blank=True)
    approved_by = models.ForeignKey(
        "db.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        "db.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "agent_infra_authorization_policies"
        unique_together = ("workspace", "name", "revision_number")
        ordering = ["priority", "-revision_number"]

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_status = instance.status
        return instance

    def clean(self):
        super().clean()
        if self.emergency and self.effect != PolicyEffect.DENY:
            raise ValidationError("Emergency policies must have effect 'deny'.")
        if self.emergency and self.priority != 0:
            raise ValidationError("Emergency policies must have priority 0.")
        if not self._state.adding and hasattr(self, "_original_status"):
            if self.status != self._original_status:
                validate_policy_status_transition(self._original_status, self.status)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} v{self.revision_number} ({self.status})"
