# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models, transaction

from plane.db.models.base import BaseModel


class RevisionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    SUPERSEDED = "superseded", "Superseded"
    RETIRED = "retired", "Retired"


class DriftStatus(models.TextChoices):
    IN_SYNC = "in_sync", "In Sync"
    DRIFTED = "drifted", "Drifted"
    UNKNOWN = "unknown", "Unknown"


class EnvironmentRevision(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="environment_revisions")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="environment_revisions")
    environment_ref = models.CharField(max_length=255)
    revision_number = models.PositiveIntegerField()
    content_hash = models.CharField(max_length=64)
    snapshot = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=RevisionStatus.choices,
        default=RevisionStatus.DRAFT,
    )
    drift_status = models.CharField(
        max_length=20,
        choices=DriftStatus.choices,
        default=DriftStatus.UNKNOWN,
    )
    drift_detail = models.JSONField(null=True, blank=True)
    last_drift_check_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_infra_environment_revision"
        unique_together = ("workspace", "project", "environment_ref", "revision_number")
        ordering = ["-revision_number"]

    @classmethod
    def allocate_next_revision_number(cls, workspace_id, project_id, environment_ref):
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
                environment_ref=environment_ref,
            )
            .order_by("-revision_number")
            .first()
        )
        return (last.revision_number + 1) if last else 1

    def activate(self):
        from plane.db.models import Project

        with transaction.atomic():
            Project.objects.select_for_update().filter(pk=self.project_id).first()

            EnvironmentRevision.objects.filter(
                workspace_id=self.workspace_id,
                project_id=self.project_id,
                environment_ref=self.environment_ref,
                status=RevisionStatus.ACTIVE,
            ).update(status=RevisionStatus.SUPERSEDED)
            self.status = RevisionStatus.ACTIVE
            self.save(update_fields=["status", "updated_at"])
