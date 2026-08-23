# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.utils import timezone

from plane.agent_infra.models import AgentRun, ContextManifest, KnowledgeVersion, VersionStatus

_context_manifest_service = None


def get_context_manifest_service() -> "ContextManifestService":
    global _context_manifest_service
    if _context_manifest_service is None:
        _context_manifest_service = ContextManifestService()
    return _context_manifest_service


class ContextManifestService:
    """Manages the binding of knowledge versions to agent runs."""

    def bind_versions_to_run(self, run, version_ids):
        """Bind a set of knowledge versions to an agent run.

        Validates all versions belong to the same workspace/project as the run.
        Creates ContextManifest entries.
        """
        if not version_ids:
            return []

        versions = list(
            KnowledgeVersion.objects.filter(pk__in=version_ids).select_related("source")
        )
        if len(versions) != len(set(version_ids)):
            found_ids = {str(version.id) for version in versions}
            missing_ids = [str(version_id) for version_id in version_ids if str(version_id) not in found_ids]
            raise ValidationError(f"Unknown knowledge version IDs: {', '.join(missing_ids)}")

        for version in versions:
            if version.workspace_id != run.workspace_id or version.project_id != run.project_id:
                raise ValidationError(
                    "Knowledge version "
                    f"{version.id} belongs to a different workspace/project than run {run.id}."
                )

        manifests = []
        for version in versions:
            manifest, _created = ContextManifest.objects.get_or_create(
                run=run,
                knowledge_version=version,
                defaults={
                    "workspace_id": run.workspace_id,
                    "project_id": run.project_id,
                },
            )
            manifests.append(manifest)
        return manifests

    def get_run_manifest(self, run_id):
        """Get all knowledge versions used by a specific run."""
        manifests = (
            ContextManifest.objects.filter(run_id=run_id)
            .select_related("knowledge_version", "knowledge_version__source")
            .order_by("bound_at")
        )
        return [manifest.knowledge_version for manifest in manifests]

    def get_downstream_impact(self, version_id):
        """Find all runs that used a specific knowledge version."""
        run_ids = (
            ContextManifest.objects.filter(knowledge_version_id=version_id)
            .values_list("run_id", flat=True)
            .distinct()
        )
        return list(AgentRun.objects.filter(pk__in=run_ids).order_by("-started_at"))

    def check_manifest_freshness(self, run_id):
        """Check if any knowledge versions used by a run have been
        superseded, quarantined, or their source has expired since binding.

        Returns: (is_fresh, stale_items: list[dict])
        """
        manifests = ContextManifest.objects.filter(run_id=run_id).select_related(
            "knowledge_version",
            "knowledge_version__source",
        )
        now = timezone.now()
        stale_items = []

        for manifest in manifests:
            version = manifest.knowledge_version
            source = version.source

            if version.status == VersionStatus.SUPERSEDED:
                stale_items.append(
                    {
                        "version_id": str(version.id),
                        "source_id": str(source.id),
                        "issue_type": "superseded",
                        "bound_at": manifest.bound_at.isoformat(),
                        "current_status": version.status,
                    }
                )
                continue

            if version.status == VersionStatus.QUARANTINED:
                stale_items.append(
                    {
                        "version_id": str(version.id),
                        "source_id": str(source.id),
                        "issue_type": "quarantined",
                        "bound_at": manifest.bound_at.isoformat(),
                        "current_status": version.status,
                    }
                )
                continue

            if source.expires_at and source.expires_at <= now:
                stale_items.append(
                    {
                        "version_id": str(version.id),
                        "source_id": str(source.id),
                        "issue_type": "source_expired",
                        "bound_at": manifest.bound_at.isoformat(),
                        "expires_at": source.expires_at.isoformat(),
                    }
                )

        return len(stale_items) == 0, stale_items
