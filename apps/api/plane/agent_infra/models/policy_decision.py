# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.base import BaseModel


class DecisionOutcome(models.TextChoices):
    ALLOW = "allow", "Allow"
    DENY = "deny", "Deny"
    REQUIRE_APPROVAL = "require_approval", "Require Approval"


class PolicyDecision(BaseModel):
    """Immutable record of every policy evaluation.

    Every time the policy engine is invoked, it creates a PolicyDecision
    with full evidence of which policies matched, what the outcome was,
    and why. This provides the deterministic audit trail required by P7.
    """

    workspace = models.ForeignKey(
        "db.Workspace", on_delete=models.CASCADE, related_name="policy_decisions"
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="policy_decisions",
    )
    subject_type = models.CharField(max_length=50)
    subject_ref = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=50)
    resource_ref = models.CharField(max_length=255)
    action = models.CharField(max_length=100)
    outcome = models.CharField(max_length=20, choices=DecisionOutcome.choices)
    matching_policies = models.JSONField(
        help_text="List of policy IDs that matched, in evaluation order"
    )
    deciding_policy = models.ForeignKey(
        "agent_infra.AuthorizationPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decisions",
        help_text="The policy that determined the final outcome",
    )
    evaluation_context = models.JSONField(
        null=True,
        blank=True,
        help_text="Snapshot of context evaluated (risk_level, conditions, etc.)",
    )
    reason = models.TextField(
        help_text="Human-readable explanation of why this outcome was reached"
    )
    evaluated_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True,
        help_text="Links to the run/assignment that triggered evaluation"
    )
    run = models.ForeignKey(
        "agent_infra.AgentRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="policy_decisions",
    )

    class Meta:
        db_table = "agent_infra_policy_decisions"
        ordering = ("-evaluated_at",)
        indexes = [
            models.Index(fields=["workspace", "subject_type", "subject_ref"], name="agent_infra_pd_subj_idx"),
            models.Index(fields=["workspace", "resource_type", "action"], name="agent_infra_pd_res_act_idx"),
        ]

    def __str__(self):
        return f"{self.subject_ref}/{self.action}/{self.resource_ref} → {self.outcome}"
