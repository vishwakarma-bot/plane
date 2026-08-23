# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class DispositionChoice(models.TextChoices):
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    REWORK = "rework", "Rework"


class ReviewDisposition(BaseModel):
    run = models.OneToOneField(
        "agent_infra.AgentRun",
        on_delete=models.CASCADE,
        related_name="review_disposition",
    )
    reviewer = models.ForeignKey(
        "db.User",
        on_delete=models.CASCADE,
        related_name="agent_review_dispositions",
    )
    disposition = models.CharField(max_length=50, choices=DispositionChoice.choices)
    reason = models.TextField()
    reviewed_at = models.DateTimeField()

    class Meta:
        verbose_name = "Review Disposition"
        verbose_name_plural = "Review Dispositions"
        db_table = "agent_infra_review_dispositions"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.disposition} for run {self.run_id}"
