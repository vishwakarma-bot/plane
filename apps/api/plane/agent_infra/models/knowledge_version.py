# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.core.exceptions import ValidationError
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class VersionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    REVIEW = "review", "Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    SUPERSEDED = "superseded", "Superseded"
    QUARANTINED = "quarantined", "Quarantined"


VALID_VERSION_TRANSITIONS: dict[str, set[str]] = {
    VersionStatus.DRAFT: {VersionStatus.REVIEW, VersionStatus.REJECTED},
    VersionStatus.REVIEW: {VersionStatus.APPROVED, VersionStatus.REJECTED, VersionStatus.DRAFT},
    VersionStatus.APPROVED: {VersionStatus.SUPERSEDED, VersionStatus.QUARANTINED},
    VersionStatus.REJECTED: {VersionStatus.DRAFT},
    VersionStatus.SUPERSEDED: set(),
    VersionStatus.QUARANTINED: {VersionStatus.REVIEW, VersionStatus.REJECTED},
}


def validate_version_status_transition(
    current: str,
    new: str,
    *,
    is_agent_generated: bool = False,
) -> None:
    """Raise ValidationError if the version status transition is not allowed."""
    if current == new:
        return

    allowed = VALID_VERSION_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValidationError(
            {
                "status": (
                    f"Invalid status transition from '{current}' to '{new}'. "
                    f"Allowed: {sorted(allowed) if allowed else '(terminal)'}"
                )
            }
        )

    if is_agent_generated and new == VersionStatus.APPROVED and current != VersionStatus.REVIEW:
        raise ValidationError(
            {
                "status": (
                    "Agent-generated knowledge versions must transition through "
                    "'review' before they can be approved."
                )
            }
        )


class KnowledgeVersion(BaseModel):
    source = models.ForeignKey(
        "agent_infra.KnowledgeSource",
        on_delete=models.CASCADE,
        related_name="versions",
    )
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="knowledge_versions")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="knowledge_versions")
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=50,
        choices=VersionStatus.choices,
        default=VersionStatus.DRAFT,
    )
    content_hash = models.CharField(max_length=64)
    diff_summary = models.TextField(blank=True)
    is_agent_generated = models.BooleanField(default=False)
    promoted_by = models.ForeignKey(
        "db.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promoted_knowledge_versions",
    )
    promoted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Knowledge Version"
        verbose_name_plural = "Knowledge Versions"
        db_table = "agent_infra_knowledge_versions"
        ordering = ("-version_number",)
        unique_together = ("source", "version_number")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["source", "status"]),
        ]

    def clean(self):
        super().clean()
        if self._state.adding:
            if self.is_agent_generated and self.status != VersionStatus.QUARANTINED:
                raise ValidationError(
                    {
                        "status": (
                            "Agent-generated knowledge versions must enter with "
                            "status 'quarantined'."
                        )
                    }
                )
            return

        if not self.pk:
            return

        previous = KnowledgeVersion.objects.filter(pk=self.pk).values(
            "status",
            "is_agent_generated",
        ).first()
        if not previous:
            return

        previous_status = previous["status"]
        if previous_status != self.status:
            validate_version_status_transition(
                previous_status,
                self.status,
                is_agent_generated=previous["is_agent_generated"],
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.source_id} v{self.version_number} ({self.status})"
