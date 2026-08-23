# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraAttentionItem,
    AssignmentType,
    AuthorityType,
    KnowledgeSource,
    KnowledgeVersion,
    SourceType,
    VersionStatus,
)
from plane.agent_infra.services.knowledge_authority import KnowledgeAuthorityService
from plane.db.models import Issue, ProjectMember, State
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory


@pytest.fixture
def knowledge_setup(db):
    user = UserFactory()
    workspace = WorkspaceFactory(owner=user)
    project = ProjectFactory(workspace=workspace, created_by=user, is_agent_infra_enabled=True)
    ProjectMember.objects.create(
        project=project,
        member=user,
        role=20,
        is_active=True,
    )
    state = State.objects.create(
        name="Todo",
        project=project,
        workspace=workspace,
        group="backlog",
        default=True,
    )
    issue = Issue.objects.create(
        name="Knowledge Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
    )
    assignment = AgentAssignment.objects.create(
        workspace=workspace,
        project=project,
        work_item=issue,
        agent_ref="agent/knowledge-test",
        assignment_type=AssignmentType.DEVELOPMENT,
        created_by=user,
    )
    source = KnowledgeSource.objects.create(
        workspace=workspace,
        project=project,
        name="Architecture Guide",
        source_type=SourceType.PLANE,
        authority_type=AuthorityType.ARCHITECTURE,
        created_by=user,
    )
    return {
        "user": user,
        "workspace": workspace,
        "project": project,
        "assignment": assignment,
        "source": source,
    }


def create_version(source, version_number, status=VersionStatus.APPROVED, **kwargs):
    return KnowledgeVersion.objects.create(
        source=source,
        workspace=source.workspace,
        project=source.project,
        version_number=version_number,
        status=status,
        content_hash=f"hash-{version_number}",
        **kwargs,
    )


@pytest.mark.unit
class TestKnowledgeAuthorityService:
    @pytest.mark.django_db
    def test_detect_authority_conflict_with_two_approved_versions(self, knowledge_setup):
        source = knowledge_setup["source"]
        create_version(source, 1)
        create_version(source, 2)

        service = KnowledgeAuthorityService()
        conflicts = service.check_authority_conflict(
            knowledge_setup["workspace"].id,
            knowledge_setup["project"].id,
            source.id,
        )

        assert len(conflicts) == 1
        assert conflicts[0]["version_a_number"] == 1
        assert conflicts[0]["version_b_number"] == 2

    @pytest.mark.django_db
    def test_no_conflict_when_single_approved_version(self, knowledge_setup):
        source = knowledge_setup["source"]
        create_version(source, 1)

        service = KnowledgeAuthorityService()
        conflicts = service.check_authority_conflict(
            knowledge_setup["workspace"].id,
            knowledge_setup["project"].id,
            source.id,
        )

        assert conflicts == []

    @pytest.mark.django_db
    def test_detect_stale_source_past_expiry(self, knowledge_setup):
        source = knowledge_setup["source"]
        with freeze_time("2026-08-01T00:00:00Z"):
            source.expires_at = timezone.now() - timedelta(days=3)
            source.save(update_fields=["expires_at", "updated_at"])

        service = KnowledgeAuthorityService()
        with freeze_time("2026-08-23T00:00:00Z"):
            stale_sources = service.check_staleness(
                knowledge_setup["workspace"].id,
                knowledge_setup["project"].id,
            )

        assert len(stale_sources) == 1
        assert stale_sources[0]["source_id"] == str(source.id)
        assert stale_sources[0]["is_expired"] is True
        assert stale_sources[0]["days_overdue"] >= 20

    @pytest.mark.django_db
    def test_no_staleness_when_source_not_expired(self, knowledge_setup):
        source = knowledge_setup["source"]
        source.expires_at = timezone.now() + timedelta(days=30)
        source.save(update_fields=["expires_at", "updated_at"])

        service = KnowledgeAuthorityService()
        stale_sources = service.check_staleness(
            knowledge_setup["workspace"].id,
            knowledge_setup["project"].id,
        )

        assert stale_sources == []

    @pytest.mark.django_db
    def test_agent_generated_cannot_auto_promote(self, knowledge_setup):
        source = knowledge_setup["source"]
        version = create_version(
            source,
            1,
            status=VersionStatus.QUARANTINED,
            is_agent_generated=True,
        )

        service = KnowledgeAuthorityService()
        is_valid, message = service.validate_promotion(version, target_status=VersionStatus.APPROVED)

        assert is_valid is False
        assert "reviewed before approval" in message

    @pytest.mark.django_db
    def test_human_can_promote_after_review(self, knowledge_setup):
        source = knowledge_setup["source"]
        version = create_version(
            source,
            1,
            status=VersionStatus.QUARANTINED,
            is_agent_generated=True,
        )
        version.status = VersionStatus.REVIEW
        version.save(update_fields=["status", "updated_at"])

        service = KnowledgeAuthorityService()
        is_valid, message = service.validate_promotion(
            version,
            promoter_user=knowledge_setup["user"],
            target_status=VersionStatus.APPROVED,
        )

        assert is_valid is True
        assert message is None

    @pytest.mark.django_db
    def test_authority_level_overrides_similarity(self, knowledge_setup):
        user = knowledge_setup["user"]
        workspace = knowledge_setup["workspace"]
        project = knowledge_setup["project"]

        security_source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=project,
            name="Security Policy",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.SECURITY,
            created_by=user,
        )
        design_source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=project,
            name="Design Notes",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.DESIGN,
            created_by=user,
        )
        security_version = create_version(security_source, 1)
        design_version = create_version(design_source, 1)

        service = KnowledgeAuthorityService()
        assert service.enforce_authority_level(security_version) is True
        assert service.should_prefer_over(
            security_version,
            design_version,
            competitor_similarity_score=0.99,
            knowledge_similarity_score=0.50,
        )

    @pytest.mark.django_db
    def test_staleness_blocks_assignment_validation(self, knowledge_setup):
        source = knowledge_setup["source"]
        source.expires_at = timezone.now() - timedelta(days=1)
        source.save(update_fields=["expires_at", "updated_at"])

        service = KnowledgeAuthorityService()
        is_valid, issues = service.validate_assignment_context(knowledge_setup["assignment"])

        assert is_valid is False
        assert any(issue["issue_type"] == "knowledge_stale" for issue in issues)

    @pytest.mark.django_db
    def test_check_project_knowledge_health_creates_attention_items(self, knowledge_setup):
        source = knowledge_setup["source"]
        source.expires_at = timezone.now() - timedelta(days=1)
        source.save(update_fields=["expires_at", "updated_at"])
        create_version(source, 1)
        create_version(source, 2)
        create_version(
            source,
            3,
            status=VersionStatus.QUARANTINED,
            is_agent_generated=True,
        )

        service = KnowledgeAuthorityService()
        summary = service.check_project_knowledge_health(
            knowledge_setup["workspace"].id,
            knowledge_setup["project"].id,
        )

        assert summary["stale_count"] == 1
        assert summary["conflict_count"] == 1
        assert summary["quarantine_count"] == 1
        assert AgentInfraAttentionItem.objects.filter(drift_type="knowledge_stale").exists()
        assert AgentInfraAttentionItem.objects.filter(drift_type="knowledge_conflict").exists()
        assert AgentInfraAttentionItem.objects.filter(drift_type="knowledge_quarantine").exists()
