# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
from datetime import timedelta

from django.db import models
from django.db.models import Count
from django.utils import timezone

from plane.agent_infra.models import (
    AgentInfraAttentionItem,
    AuthorityType,
    KnowledgeSource,
    KnowledgeVersion,
    VersionStatus,
)

logger = logging.getLogger("plane.worker")

_knowledge_authority_service = None

AUTHORITY_RANK = {
    AuthorityType.SECURITY: 7,
    AuthorityType.ARCHITECTURE: 6,
    AuthorityType.PLATFORM: 5,
    AuthorityType.RELEASE: 4,
    AuthorityType.QA: 3,
    AuthorityType.PRODUCT: 2,
    AuthorityType.DESIGN: 1,
}

STALE_APPROACHING_DAYS = 7


def get_knowledge_authority_service() -> "KnowledgeAuthorityService":
    global _knowledge_authority_service
    if _knowledge_authority_service is None:
        _knowledge_authority_service = KnowledgeAuthorityService()
    return _knowledge_authority_service


class KnowledgeAuthorityService:
    """Enforces knowledge authority rules and detects conflicts/staleness."""

    def check_authority_conflict(self, workspace_id, project_id, source_id):
        """Detect if two approved versions exist for the same source."""
        approved_versions = list(
            KnowledgeVersion.objects.filter(
                workspace_id=workspace_id,
                project_id=project_id,
                source_id=source_id,
                status=VersionStatus.APPROVED,
            ).order_by("version_number")
        )

        if len(approved_versions) < 2:
            return []

        conflicts = []
        for index in range(len(approved_versions)):
            for other_index in range(index + 1, len(approved_versions)):
                first = approved_versions[index]
                second = approved_versions[other_index]
                conflicts.append(
                    {
                        "source_id": str(source_id),
                        "version_a_id": str(first.id),
                        "version_a_number": first.version_number,
                        "version_b_id": str(second.id),
                        "version_b_number": second.version_number,
                    }
                )
        return conflicts

    def check_staleness(self, workspace_id, project_id):
        """Find sources that are expired or approaching expiry."""
        now = timezone.now()
        approaching_threshold = now + timedelta(days=STALE_APPROACHING_DAYS)

        sources = KnowledgeSource.objects.filter(
            workspace_id=workspace_id,
            project_id=project_id,
            is_retired=False,
            expires_at__isnull=False,
        )

        stale_sources = []
        for source in sources:
            if source.expires_at <= now:
                days_overdue = (now - source.expires_at).days
                stale_sources.append(
                    {
                        "source_id": str(source.id),
                        "source_name": source.name,
                        "expires_at": source.expires_at.isoformat(),
                        "days_overdue": days_overdue,
                        "is_expired": True,
                    }
                )
            elif source.expires_at <= approaching_threshold:
                days_until_expiry = (source.expires_at - now).days
                stale_sources.append(
                    {
                        "source_id": str(source.id),
                        "source_name": source.name,
                        "expires_at": source.expires_at.isoformat(),
                        "days_overdue": -days_until_expiry,
                        "is_expired": False,
                    }
                )

        return stale_sources

    def validate_assignment_context(self, assignment):
        """Check if any knowledge sources used by this assignment's agent are stale or conflicting.

        This is called during assignment creation/claim to ensure the agent
        has access to valid, non-stale knowledge.

        Returns: (is_valid, issues: list[dict])
        """
        workspace_id = assignment.workspace_id
        project_id = assignment.project_id
        issues = []

        stale_sources = self.check_staleness(workspace_id, project_id)
        for stale_source in stale_sources:
            if stale_source["is_expired"]:
                issues.append(
                    {
                        "issue_type": "knowledge_stale",
                        "source_id": stale_source["source_id"],
                        "message": f"Knowledge source '{stale_source['source_name']}' expired "
                        f"{stale_source['days_overdue']} day(s) ago.",
                        **stale_source,
                    }
                )

        conflicting_source_ids = (
            KnowledgeVersion.objects.filter(
                workspace_id=workspace_id,
                project_id=project_id,
                status=VersionStatus.APPROVED,
            )
            .values("source_id")
            .annotate(approved_count=Count("id"))
            .filter(approved_count__gt=1)
            .values_list("source_id", flat=True)
        )

        for source_id in conflicting_source_ids:
            conflicts = self.check_authority_conflict(workspace_id, project_id, source_id)
            for conflict in conflicts:
                issues.append(
                    {
                        "issue_type": "knowledge_conflict",
                        "message": (
                            f"Conflicting approved versions v{conflict['version_a_number']} "
                            f"and v{conflict['version_b_number']} for source {source_id}."
                        ),
                        **conflict,
                    }
                )

        return len(issues) == 0, issues

    def enforce_authority_level(self, knowledge_version, vector_similarity_score=None):
        """Ensure authority level takes precedence over vector similarity.

        Gate P4: "vector similarity cannot override authority"
        An approved authoritative version at a higher authority level
        MUST be preferred over a vector-similar but lower-authority version.
        """
        _ = vector_similarity_score  # ignored by policy when authority applies
        if knowledge_version.status != VersionStatus.APPROVED:
            return False

        authority_type = knowledge_version.source.authority_type
        return AUTHORITY_RANK.get(authority_type, 0) > 0

    def should_prefer_over(
        self,
        knowledge_version,
        competitor_version,
        competitor_similarity_score,
        knowledge_similarity_score=None,
    ):
        """Return True when authority policy selects knowledge_version over competitor."""
        if not self.enforce_authority_level(knowledge_version):
            return False

        version_rank = AUTHORITY_RANK.get(knowledge_version.source.authority_type, 0)
        competitor_rank = AUTHORITY_RANK.get(competitor_version.source.authority_type, 0)

        if version_rank > competitor_rank:
            return True
        if version_rank < competitor_rank:
            return False

        version_similarity = knowledge_similarity_score if knowledge_similarity_score is not None else 0.0
        return version_similarity >= competitor_similarity_score

    def validate_promotion(self, knowledge_version, promoter_user=None, target_status=VersionStatus.APPROVED):
        """Gate P4: "Agent output cannot auto-promote"

        Agent-generated versions (is_agent_generated=True) cannot transition
        from quarantined to approved without going through review first.
        A human must explicitly promote.
        """
        if not knowledge_version.is_agent_generated:
            return True, None

        if knowledge_version.status == VersionStatus.QUARANTINED:
            if target_status == VersionStatus.APPROVED:
                return False, "Agent-generated content must be reviewed before approval"
            if target_status not in {VersionStatus.REVIEW, VersionStatus.REJECTED}:
                return False, "Agent-generated content must be reviewed before approval"

        if target_status == VersionStatus.APPROVED and not promoter_user:
            return False, "Agent-generated content requires human promotion"

        return True, None

    def create_knowledge_attention_item(self, entity, drift_type, details):
        """Create or update an attention item for knowledge drift."""
        workspace_id = getattr(entity, "workspace_id", None)
        project_id = getattr(entity, "project_id", None)

        if workspace_id is None or project_id is None:
            source = getattr(entity, "source", None)
            if source is not None:
                workspace_id = source.workspace_id
                project_id = source.project_id

        attention_item, _created = AgentInfraAttentionItem.objects.get_or_create(
            workspace_id=workspace_id,
            project_id=project_id,
            entity_type=entity.__class__.__name__,
            entity_id=entity.id,
            drift_type=drift_type,
            resolved_at=None,
            defaults={"details": details},
        )
        if not _created and attention_item.details != details:
            attention_item.details = details
            attention_item.save(update_fields=["details", "updated_at"])

        logger.info(
            "Knowledge drift detected",
            extra={
                "drift_type": drift_type,
                "entity_type": attention_item.entity_type,
                "entity_id": str(attention_item.entity_id),
            },
        )
        return attention_item

    def record_staleness_attention_items(self, workspace_id, project_id):
        """Create attention items for expired knowledge sources."""
        attention_items = []
        for stale_source in self.check_staleness(workspace_id, project_id):
            if not stale_source["is_expired"]:
                continue

            source = KnowledgeSource.objects.get(pk=stale_source["source_id"])
            attention_items.append(
                self.create_knowledge_attention_item(
                    entity=source,
                    drift_type="knowledge_stale",
                    details=stale_source,
                )
            )
        return attention_items

    def record_conflict_attention_items(self, workspace_id, project_id):
        """Create attention items for authority conflicts."""
        attention_items = []
        conflicting_source_ids = (
            KnowledgeVersion.objects.filter(
                workspace_id=workspace_id,
                project_id=project_id,
                status=VersionStatus.APPROVED,
            )
            .values("source_id")
            .annotate(approved_count=Count("id"))
            .filter(approved_count__gt=1)
            .values_list("source_id", flat=True)
        )

        for source_id in conflicting_source_ids:
            source = KnowledgeSource.objects.get(pk=source_id)
            conflicts = self.check_authority_conflict(workspace_id, project_id, source_id)
            for conflict in conflicts:
                attention_items.append(
                    self.create_knowledge_attention_item(
                        entity=source,
                        drift_type="knowledge_conflict",
                        details=conflict,
                    )
                )
        return attention_items

    def record_quarantine_attention_items(self, workspace_id, project_id):
        """Create attention items for quarantined versions needing review."""
        attention_items = []
        quarantined_versions = KnowledgeVersion.objects.filter(
            workspace_id=workspace_id,
            project_id=project_id,
            status=VersionStatus.QUARANTINED,
        ).select_related("source")

        for version in quarantined_versions:
            attention_items.append(
                self.create_knowledge_attention_item(
                    entity=version,
                    drift_type="knowledge_quarantine",
                    details={
                        "version_id": str(version.id),
                        "source_id": str(version.source_id),
                        "source_name": version.source.name,
                        "version_number": version.version_number,
                        "is_agent_generated": version.is_agent_generated,
                    },
                )
            )
        return attention_items

    def check_project_knowledge_health(self, workspace_id, project_id):
        """Detect stale/conflicting/quarantined knowledge and create attention items."""
        stale_items = self.record_staleness_attention_items(workspace_id, project_id)
        conflict_items = self.record_conflict_attention_items(workspace_id, project_id)
        quarantine_items = self.record_quarantine_attention_items(workspace_id, project_id)

        return {
            "stale_count": len(stale_items),
            "conflict_count": len(conflict_items),
            "quarantine_count": len(quarantine_items),
        }

    def resolve_context(self, project, query="", max_results=10):
        """Resolve knowledge context for a project, prioritizing authority over similarity.

        Returns a list of knowledge versions ordered by authority weight,
        with only approved versions from non-retired, non-expired sources.
        """
        from django.utils import timezone

        now = timezone.now()

        eligible_versions = KnowledgeVersion.objects.filter(
            project=project,
            status=VersionStatus.APPROVED,
            source__is_retired=False,
        ).filter(
            models.Q(source__expires_at__isnull=True) | models.Q(source__expires_at__gt=now)
        ).select_related("source").order_by("-version_number")

        authority_order = [
            "security", "architecture", "platform", "product", "design", "qa", "release"
        ]

        def authority_rank(version):
            auth_type = version.source.authority_type
            try:
                return authority_order.index(auth_type)
            except ValueError:
                return len(authority_order)

        versions_list = list(eligible_versions[:50])
        versions_list.sort(key=authority_rank)

        results = []
        for version in versions_list[:max_results]:
            results.append({
                "version_id": str(version.id),
                "source_id": str(version.source_id),
                "source_name": version.source.name,
                "authority_type": version.source.authority_type,
                "version_number": version.version_number,
                "content_hash": version.content_hash,
                "diff_summary": version.diff_summary,
            })

        return {
            "project_id": str(project.id),
            "query": query,
            "results": results,
            "total_eligible": len(versions_list),
        }
