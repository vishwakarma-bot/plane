# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from plane.agent_infra.models import CatalogRevision, CatalogRevisionStatus


class CatalogVersioningService:
    @staticmethod
    def compute_diff(old_snapshot, new_snapshot):
        if old_snapshot is None:
            return {"added": list(new_snapshot.keys()), "removed": [], "changed": {}}
        added = [k for k in new_snapshot if k not in old_snapshot]
        removed = [k for k in old_snapshot if k not in new_snapshot]
        changed = {}
        for k in set(old_snapshot.keys()) & set(new_snapshot.keys()):
            if old_snapshot[k] != new_snapshot[k]:
                changed[k] = {"old": old_snapshot[k], "new": new_snapshot[k]}
        return {"added": added, "removed": removed, "changed": changed}

    @staticmethod
    def submit_for_approval(revision_id):
        with transaction.atomic():
            revision = CatalogRevision.objects.select_for_update().get(pk=revision_id)
            if revision.status != CatalogRevisionStatus.DRAFT:
                raise ValidationError(f"Cannot submit: current status is {revision.status}")
            revision.status = CatalogRevisionStatus.PENDING_APPROVAL
            revision.save(update_fields=["status", "updated_at"])
            return revision

    @staticmethod
    def approve(revision_id, user):
        with transaction.atomic():
            revision = CatalogRevision.objects.select_for_update().get(pk=revision_id)
            if revision.status != CatalogRevisionStatus.PENDING_APPROVAL:
                raise ValidationError(f"Cannot approve: current status is {revision.status}")
            if revision.created_by_id is None:
                raise ValidationError(
                    "Separation of duty: cannot approve a revision with unknown creator"
                )
            if revision.created_by_id == user.id:
                raise ValidationError(
                    "Separation of duty: the revision creator cannot approve their own revision"
                )
            revision.status = CatalogRevisionStatus.APPROVED
            revision.approved_by = user
            revision.approved_at = timezone.now()
            revision.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
            return revision

    @staticmethod
    def reject(revision_id, user, reason=""):
        with transaction.atomic():
            revision = CatalogRevision.objects.select_for_update().get(pk=revision_id)
            if revision.status != CatalogRevisionStatus.PENDING_APPROVAL:
                raise ValidationError(f"Cannot reject: current status is {revision.status}")
            revision.status = CatalogRevisionStatus.REJECTED
            revision.save(update_fields=["status", "updated_at"])
            return revision

    @staticmethod
    def rollback(revision_id, user):
        with transaction.atomic():
            revision = CatalogRevision.objects.select_for_update().get(pk=revision_id)
            if revision.status != CatalogRevisionStatus.APPROVED:
                raise ValidationError(f"Cannot rollback: current status is {revision.status}")
            revision.status = CatalogRevisionStatus.ROLLED_BACK
            revision.save(update_fields=["status", "updated_at"])
            if revision.previous_revision_id:
                prev = CatalogRevision.objects.get(pk=revision.previous_revision_id)
                new_number = CatalogRevision.allocate_next_revision_number(
                    revision.workspace_id,
                    revision.project_id,
                    revision.entity_type,
                    revision.entity_ref,
                )
                new_rev = CatalogRevision.objects.create(
                    workspace_id=revision.workspace_id,
                    project_id=revision.project_id,
                    entity_type=revision.entity_type,
                    entity_ref=revision.entity_ref,
                    revision_number=new_number,
                    content_hash=prev.content_hash,
                    content_snapshot=prev.content_snapshot,
                    previous_revision=revision,
                    status=CatalogRevisionStatus.DRAFT,
                    diff_summary=CatalogVersioningService.compute_diff(
                        revision.content_snapshot, prev.content_snapshot
                    ),
                    created_by=user,
                    updated_by=user,
                )
                return new_rev
            return revision
