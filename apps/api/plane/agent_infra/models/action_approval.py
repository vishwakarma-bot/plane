# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.base import BaseModel


class ApprovalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"
    CANCELLED = "cancelled", "Cancelled"


class ActionApproval(BaseModel):
    """Exact-action approval queue entry.

    When a policy evaluates to `require_approval`, an ActionApproval record
    is created. It captures the exact action requested, including the target,
    digest/diff, credential scope, budget impact, and expiry. A human reviewer
    must approve or reject before the action can proceed.
    """

    workspace = models.ForeignKey(
        "db.Workspace", on_delete=models.CASCADE, related_name="action_approvals"
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="action_approvals",
    )
    policy_decision = models.ForeignKey(
        "agent_infra.PolicyDecision",
        on_delete=models.CASCADE,
        related_name="approval_requests",
        help_text="The policy decision that triggered this approval request",
    )
    subject_type = models.CharField(max_length=50)
    subject_ref = models.CharField(max_length=255)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50)
    target_ref = models.CharField(max_length=255)
    target_digest = models.CharField(
        max_length=128, null=True, blank=True,
        help_text="Content hash/digest of the target for integrity verification"
    )
    target_diff = models.JSONField(
        null=True, blank=True,
        help_text="Semantic diff showing what the action would change"
    )
    credential_scope = models.JSONField(
        null=True, blank=True,
        help_text="What credentials/scopes the action requires"
    )
    budget_impact = models.JSONField(
        null=True, blank=True,
        help_text="Estimated cost, token, and resource impact"
    )
    risk_level = models.CharField(
        max_length=20, default="medium",
        help_text="Risk classification of this specific action"
    )
    status = models.CharField(
        max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    requested_by = models.ForeignKey(
        "db.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_approvals",
    )
    reviewed_by = models.ForeignKey(
        "db.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_approvals",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Auto-expires if not reviewed by this time"
    )
    correlation_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    class Meta:
        db_table = "agent_infra_action_approvals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "status"], name="agent_infra_aa_ws_status_idx"),
            models.Index(fields=["workspace", "project", "status"], name="agent_infra_aa_proj_status_idx"),
        ]

    def __str__(self):
        return f"{self.subject_ref}/{self.action} → {self.target_ref} ({self.status})"

    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expires_at and self.status == ApprovalStatus.PENDING:
            return timezone.now() > self.expires_at
        return False
