# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.core.exceptions import ValidationError
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class ReviewVerdict(models.TextChoices):
    ACCEPTED = "accepted", "Accepted"
    FLAGGED = "flagged", "Flagged"
    ESCALATED = "escalated", "Escalated"


class AuthorizingReview(BaseModel):
    run = models.OneToOneField(
        "agent_infra.AgentRun",
        on_delete=models.CASCADE,
        related_name="authorizing_review",
    )
    reviewer_agent_ref = models.CharField(max_length=255)
    reviewer_model = models.CharField(max_length=255)
    verdict = models.CharField(max_length=50, choices=ReviewVerdict.choices)
    reason = models.TextField()
    reviewed_at = models.DateTimeField()

    class Meta:
        verbose_name = "Authorizing Review"
        verbose_name_plural = "Authorizing Reviews"
        db_table = "agent_infra_authorizing_reviews"
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.run_id and self.reviewer_model == self.run.model_used:
            raise ValidationError(
                {"reviewer_model": "Reviewer model must differ from the agent run model."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.verdict} for run {self.run_id}"
