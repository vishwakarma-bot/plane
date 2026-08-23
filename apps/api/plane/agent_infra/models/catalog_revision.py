# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.db import models

from plane.db.models.base import BaseModel


class CatalogEntityType(models.TextChoices):
    AGENT = "agent", "Agent"
    SKILL = "skill", "Skill"
    MODEL = "model", "Model"
    ENVIRONMENT = "environment", "Environment"
    INTEGRATION = "integration", "Integration"


class CatalogRevisionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    ROLLED_BACK = "rolled_back", "Rolled Back"


VALID_REVISION_TRANSITIONS = {
    "draft": {"pending_approval"},
    "pending_approval": {"approved", "rejected"},
    "approved": {"rolled_back"},
    "rejected": {"draft"},
    "rolled_back": set(),
}


class CatalogRevision(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="catalog_revisions")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="catalog_revisions")
    entity_type = models.CharField(max_length=20, choices=CatalogEntityType.choices)
    entity_ref = models.CharField(max_length=255)
    revision_number = models.PositiveIntegerField()
    content_hash = models.CharField(max_length=64)
    content_snapshot = models.JSONField()
    previous_revision = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_revisions",
    )
    status = models.CharField(
        max_length=20,
        choices=CatalogRevisionStatus.choices,
        default=CatalogRevisionStatus.DRAFT,
    )
    diff_summary = models.JSONField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "db.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_infra_catalog_revision"
        unique_together = ("workspace", "project", "entity_type", "entity_ref", "revision_number")
        ordering = ["-revision_number"]

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_status = instance.status
        return instance

    def clean(self):
        super().clean()
        if not self._state.adding and hasattr(self, "_original_status"):
            allowed = VALID_REVISION_TRANSITIONS.get(self._original_status, set())
            if self.status != self._original_status and self.status not in allowed:
                raise ValidationError(
                    f"Invalid revision status transition: {self._original_status} → {self.status}"
                )

    @classmethod
    def allocate_next_revision_number(cls, workspace_id, project_id, entity_type, entity_ref):
        """
        Allocate the next revision number by locking the project row.
        IMPORTANT: Must be called inside the same transaction.atomic() that
        performs the insert.
        """
        from plane.db.models import Project

        Project.objects.select_for_update().filter(pk=project_id).first()
        last = (
            cls.objects.filter(
                workspace_id=workspace_id,
                project_id=project_id,
                entity_type=entity_type,
                entity_ref=entity_ref,
            )
            .order_by("-revision_number")
            .first()
        )
        return (last.revision_number + 1) if last else 1
