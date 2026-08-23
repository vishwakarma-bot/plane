# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.utils import timezone

from plane.agent_infra.models import DriftStatus, EnvironmentRevision, RevisionStatus


class DriftDetectionService:
    @staticmethod
    def check_drift(revision_id, current_content_hash):
        """
        Compare a client-supplied content_hash against the stored revision hash.

        The content_hash is client-supplied and NOT attested by a trusted
        integration. Drift results are informational only and MUST NOT drive
        automated governance decisions.
        """
        revision = EnvironmentRevision.objects.get(pk=revision_id)
        if revision.content_hash == current_content_hash:
            drift_status = DriftStatus.IN_SYNC
            drift_detail = {"source": "client_reported"}
        else:
            drift_status = DriftStatus.DRIFTED
            drift_detail = {
                "expected_hash": revision.content_hash,
                "actual_hash": current_content_hash,
                "source": "client_reported",
            }
        revision.drift_status = drift_status
        revision.drift_detail = drift_detail
        revision.last_drift_check_at = timezone.now()
        revision.save(update_fields=["drift_status", "drift_detail", "last_drift_check_at", "updated_at"])
        return revision

    @staticmethod
    def get_drift_summary(workspace_id, project_id):
        revisions = EnvironmentRevision.objects.filter(
            workspace_id=workspace_id,
            project_id=project_id,
            status=RevisionStatus.ACTIVE,
        )
        return {
            "total": revisions.count(),
            "in_sync": revisions.filter(drift_status=DriftStatus.IN_SYNC).count(),
            "drifted": revisions.filter(drift_status=DriftStatus.DRIFTED).count(),
            "unknown": revisions.filter(drift_status=DriftStatus.UNKNOWN).count(),
        }
