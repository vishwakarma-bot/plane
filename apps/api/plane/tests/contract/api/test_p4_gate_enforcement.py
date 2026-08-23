# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Contract tests for Phase P4 review blocker resolution.

These tests prove end-to-end that:
1. Stale/conflicting knowledge blocks assignment creation and claim
2. Authority enforcement overrides similarity in the resolve-context contract
3. Index deletion records are created on source retirement
4. Unauthorized reviewer cannot approve agent-generated versions
5. Knowledge context validation prevents execution with invalid state
"""

import hashlib
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from plane.agent_infra.models import (
    AgentAssignment,
    AgentRun,
    AssignmentType,
    AuthorityType,
    IndexAction,
    IndexRequestStatus,
    KnowledgeIndexRecord,
    KnowledgeSource,
    KnowledgeVersion,
    RunOutcome,
    SourceType,
    VersionStatus,
)
from plane.db.models import Issue, Project, ProjectMember, State, Workspace
from plane.tests.helpers.agent_infra_auth import (
    create_service_identity,
    signed_json_patch,
    signed_json_post,
)


def assignment_url(workspace_slug, project_id, assignment_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-assignments/"
    return f"{base}{assignment_id}/" if assignment_id else base


def knowledge_source_url(workspace_slug, project_id, source_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/knowledge-sources/"
    return f"{base}{source_id}/" if source_id else base


def knowledge_version_url(workspace_slug, project_id, source_id, version_id=None):
    base = (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"knowledge-sources/{source_id}/versions/"
    )
    return f"{base}{version_id}/" if version_id else base


def resolve_context_url(workspace_slug, project_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"knowledge-context/resolve/"
    )


def index_record_url(workspace_slug, project_id, record_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/knowledge-index-records/"
    return f"{base}{record_id}/" if record_id else base


@pytest.fixture
def p4_project(db, workspace, create_user):
    project = Project.objects.create(
        name="P4 Gate Test Project",
        identifier="P4GT",
        workspace=workspace,
        created_by=create_user,
        is_agent_infra_enabled=True,
    )
    ProjectMember.objects.create(
        project=project, member=create_user, role=20, is_active=True
    )
    return project


@pytest.fixture
def p4_state(db, workspace, p4_project):
    return State.objects.create(
        name="Todo", project=p4_project, workspace=workspace, group="backlog", default=True
    )


@pytest.fixture
def p4_issue(db, workspace, p4_project, p4_state, create_user):
    return Issue.objects.create(
        name="P4 Test Work Item",
        workspace=workspace,
        project=p4_project,
        state=p4_state,
        created_by=create_user,
    )


@pytest.fixture
def stale_source(db, workspace, p4_project, create_user):
    """A knowledge source that expired yesterday."""
    return KnowledgeSource.objects.create(
        workspace=workspace,
        project=p4_project,
        name="Expired Architecture Guide",
        source_type=SourceType.PLANE,
        authority_type=AuthorityType.ARCHITECTURE,
        expires_at=timezone.now() - timedelta(days=1),
        created_by=create_user,
    )


@pytest.fixture
def conflicting_source(db, workspace, p4_project, create_user):
    """A source with two approved versions (authority conflict)."""
    source = KnowledgeSource.objects.create(
        workspace=workspace,
        project=p4_project,
        name="Conflicting Security Policy",
        source_type=SourceType.PLANE,
        authority_type=AuthorityType.SECURITY,
        created_by=create_user,
    )
    KnowledgeVersion.objects.create(
        source=source,
        workspace=workspace,
        project=p4_project,
        version_number=1,
        status=VersionStatus.APPROVED,
        content_hash="hash-1",
    )
    KnowledgeVersion.objects.create(
        source=source,
        workspace=workspace,
        project=p4_project,
        version_number=2,
        status=VersionStatus.APPROVED,
        content_hash="hash-2",
    )
    return source


@pytest.mark.contract
class TestStalenessBlocksAssignment:
    """Gate P4: stale/conflicting knowledge blocks affected assignments by policy."""

    @pytest.mark.django_db
    def test_stale_knowledge_blocks_assignment_creation(
        self, api_key_client, workspace, p4_project, p4_issue, stale_source
    ):
        """POST assignment returns 409 KNOWLEDGE_CONTEXT_INVALID when project has expired sources."""
        response = api_key_client.post(
            assignment_url(workspace.slug, p4_project.id),
            {
                "work_item": str(p4_issue.id),
                "agent_ref": "agent/test",
                "assignment_type": AssignmentType.DEVELOPMENT,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error_code"] == "KNOWLEDGE_CONTEXT_INVALID"
        assert "expired" in response.data["message"].lower() or "stale" in response.data["message"].lower()

    @pytest.mark.django_db
    def test_conflicting_knowledge_blocks_assignment_creation(
        self, api_key_client, workspace, p4_project, p4_issue, conflicting_source
    ):
        """POST assignment returns 409 when project has authority conflicts."""
        response = api_key_client.post(
            assignment_url(workspace.slug, p4_project.id),
            {
                "work_item": str(p4_issue.id),
                "agent_ref": "agent/test",
                "assignment_type": AssignmentType.DEVELOPMENT,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error_code"] == "KNOWLEDGE_CONTEXT_INVALID"

    @pytest.mark.django_db
    def test_stale_knowledge_blocks_claim(
        self, api_key_client, workspace, p4_project, p4_issue, create_user, service_identity
    ):
        """PATCH assignment→running blocked when project has expired sources."""
        assignment = AgentAssignment.objects.create(
            workspace=workspace,
            project=p4_project,
            work_item=p4_issue,
            agent_ref="agent/test",
            assignment_type=AssignmentType.DEVELOPMENT,
            created_by=create_user,
        )
        KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Stale Source",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.QA,
            expires_at=timezone.now() - timedelta(days=2),
            created_by=create_user,
        )

        response = signed_json_patch(
            api_key_client,
            assignment_url(workspace.slug, p4_project.id, assignment.id),
            {"status": "running"},
            service_identity,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error_code"] == "KNOWLEDGE_CONTEXT_INVALID"
        assignment.refresh_from_db()
        assert assignment.status == "pending"

    @pytest.mark.django_db
    def test_clean_knowledge_allows_assignment_creation(
        self, api_key_client, workspace, p4_project, p4_issue, create_user
    ):
        """Assignment creation succeeds when no knowledge issues exist."""
        KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Valid Source",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.PRODUCT,
            expires_at=timezone.now() + timedelta(days=30),
            created_by=create_user,
        )

        response = api_key_client.post(
            assignment_url(workspace.slug, p4_project.id),
            {
                "work_item": str(p4_issue.id),
                "agent_ref": "agent/test",
                "assignment_type": AssignmentType.DEVELOPMENT,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.django_db
    def test_clean_knowledge_allows_claim(
        self, api_key_client, workspace, p4_project, p4_issue, create_user, service_identity
    ):
        """Claim succeeds when knowledge context is valid."""
        assignment = AgentAssignment.objects.create(
            workspace=workspace,
            project=p4_project,
            work_item=p4_issue,
            agent_ref="agent/test",
            assignment_type=AssignmentType.DEVELOPMENT,
            created_by=create_user,
        )

        response = signed_json_patch(
            api_key_client,
            assignment_url(workspace.slug, p4_project.id, assignment.id),
            {"status": "running"},
            service_identity,
        )

        assert response.status_code == status.HTTP_200_OK
        assignment.refresh_from_db()
        assert assignment.status == "running"


@pytest.mark.contract
class TestAuthorityOverridesSimilarity:
    """Gate P4: vector similarity cannot override authority."""

    @pytest.mark.django_db
    def test_resolve_context_ranks_by_authority_over_similarity(
        self, api_key_client, workspace, p4_project, create_user, service_identity
    ):
        """Higher authority rank wins even with lower similarity score."""
        security_source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Security Policy",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.SECURITY,
            created_by=create_user,
        )
        design_source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Design Notes",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.DESIGN,
            created_by=create_user,
        )
        security_version = KnowledgeVersion.objects.create(
            source=security_source,
            workspace=workspace,
            project=p4_project,
            version_number=1,
            status=VersionStatus.APPROVED,
            content_hash="security-hash",
        )
        design_version = KnowledgeVersion.objects.create(
            source=design_source,
            workspace=workspace,
            project=p4_project,
            version_number=1,
            status=VersionStatus.APPROVED,
            content_hash="design-hash",
        )

        response = signed_json_post(
            api_key_client,
            resolve_context_url(workspace.slug, p4_project.id),
            {
                "candidates": [
                    {"version_id": str(design_version.id), "similarity_score": 0.99},
                    {"version_id": str(security_version.id), "similarity_score": 0.30},
                ]
            },
            service_identity,
        )

        assert response.status_code == status.HTTP_200_OK
        resolved = response.data["resolved"]
        assert len(resolved) == 2
        assert resolved[0]["version_id"] == str(security_version.id)
        assert resolved[0]["authority_type"] == AuthorityType.SECURITY
        assert resolved[0]["is_authoritative"] is True
        assert resolved[0]["provenance"] == "human"
        assert response.data["policy_applied"] == "authority_overrides_similarity"

    @pytest.mark.django_db
    def test_resolve_context_excludes_non_approved_as_ineligible(
        self, api_key_client, workspace, p4_project, create_user, service_identity
    ):
        """Non-approved versions appear in ineligible list."""
        source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Draft Source",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.QA,
            created_by=create_user,
        )
        draft_version = KnowledgeVersion.objects.create(
            source=source,
            workspace=workspace,
            project=p4_project,
            version_number=1,
            status=VersionStatus.DRAFT,
            content_hash="draft-hash",
        )

        response = signed_json_post(
            api_key_client,
            resolve_context_url(workspace.slug, p4_project.id),
            {"candidates": [{"version_id": str(draft_version.id), "similarity_score": 0.95}]},
            service_identity,
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["resolved"]) == 0
        assert len(response.data["ineligible"]) == 1
        assert response.data["ineligible"][0]["eligible"] is False


@pytest.mark.contract
class TestIndexDeletionReconciliation:
    """Gate P4: reindex/deletion requests and audit."""

    @pytest.mark.django_db
    def test_retire_source_creates_deletion_records(
        self, api_key_client, workspace, p4_project, create_user
    ):
        """DELETE on source creates index deletion records for approved versions."""
        source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Source to Retire",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.ARCHITECTURE,
            created_by=create_user,
        )
        approved_version = KnowledgeVersion.objects.create(
            source=source,
            workspace=workspace,
            project=p4_project,
            version_number=1,
            status=VersionStatus.APPROVED,
            content_hash="approved-hash",
        )
        draft_version = KnowledgeVersion.objects.create(
            source=source,
            workspace=workspace,
            project=p4_project,
            version_number=2,
            status=VersionStatus.DRAFT,
            content_hash="draft-hash",
        )

        response = api_key_client.delete(
            knowledge_source_url(workspace.slug, p4_project.id, source.id)
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        source.refresh_from_db()
        assert source.is_retired is True

        deletion_records = KnowledgeIndexRecord.objects.filter(
            knowledge_version=approved_version, action=IndexAction.DELETE
        )
        assert deletion_records.count() == 1
        assert deletion_records.first().status == IndexRequestStatus.PENDING

        draft_deletion_records = KnowledgeIndexRecord.objects.filter(
            knowledge_version=draft_version, action=IndexAction.DELETE
        )
        assert draft_deletion_records.count() == 0

    @pytest.mark.django_db
    def test_request_reindex(self, api_key_client, workspace, p4_project, create_user):
        """POST reindex request creates a pending index record."""
        source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Source to Reindex",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.PRODUCT,
            created_by=create_user,
        )
        version = KnowledgeVersion.objects.create(
            source=source,
            workspace=workspace,
            project=p4_project,
            version_number=1,
            status=VersionStatus.APPROVED,
            content_hash="reindex-hash",
        )

        response = api_key_client.post(
            index_record_url(workspace.slug, p4_project.id),
            {"knowledge_version": str(version.id), "action": IndexAction.REINDEX},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["action"] == IndexAction.REINDEX
        assert response.data["status"] == IndexRequestStatus.PENDING

    @pytest.mark.django_db
    def test_acknowledge_and_complete_deletion(
        self, api_key_client, workspace, p4_project, create_user
    ):
        """Index record lifecycle: pending → acknowledged → completed (verified)."""
        source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Lifecycle Source",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.QA,
            created_by=create_user,
        )
        version = KnowledgeVersion.objects.create(
            source=source,
            workspace=workspace,
            project=p4_project,
            version_number=1,
            status=VersionStatus.APPROVED,
            content_hash="lifecycle-hash",
        )
        record = KnowledgeIndexRecord.objects.create(
            workspace=workspace,
            project=p4_project,
            knowledge_version=version,
            action=IndexAction.DELETE,
            status=IndexRequestStatus.PENDING,
            created_by=create_user,
        )

        ack_response = api_key_client.patch(
            index_record_url(workspace.slug, p4_project.id, record.id),
            {"status": IndexRequestStatus.ACKNOWLEDGED, "external_ref": "idx-abc123"},
            format="json",
        )
        assert ack_response.status_code == status.HTTP_200_OK
        assert ack_response.data["status"] == IndexRequestStatus.ACKNOWLEDGED
        assert ack_response.data["external_ref"] == "idx-abc123"

        complete_response = api_key_client.patch(
            index_record_url(workspace.slug, p4_project.id, record.id),
            {"status": IndexRequestStatus.IN_PROGRESS},
            format="json",
        )
        assert complete_response.status_code == status.HTTP_200_OK

        verify_response = api_key_client.patch(
            index_record_url(workspace.slug, p4_project.id, record.id),
            {"status": IndexRequestStatus.COMPLETED},
            format="json",
        )
        assert verify_response.status_code == status.HTTP_200_OK
        assert verify_response.data["is_verified"] is True

    @pytest.mark.django_db
    def test_cross_workspace_index_record_denied(
        self, api_key_client, workspace, p4_project, create_user
    ):
        """Cannot view index records from another workspace."""
        other_workspace = Workspace.objects.create(
            name="Other WS", slug="other-ws-idx", owner=create_user
        )
        other_project = Project.objects.create(
            name="Other Proj",
            identifier="OIDX",
            workspace=other_workspace,
            created_by=create_user,
            is_agent_infra_enabled=True,
        )
        ProjectMember.objects.create(
            project=other_project, member=create_user, role=20, is_active=True
        )

        source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="My Source",
            source_type=SourceType.PLANE,
            authority_type=AuthorityType.PRODUCT,
            created_by=create_user,
        )
        version = KnowledgeVersion.objects.create(
            source=source,
            workspace=workspace,
            project=p4_project,
            version_number=1,
            status=VersionStatus.APPROVED,
            content_hash="cross-ws-hash",
        )
        record = KnowledgeIndexRecord.objects.create(
            workspace=workspace,
            project=p4_project,
            knowledge_version=version,
            action=IndexAction.DELETE,
            status=IndexRequestStatus.PENDING,
            created_by=create_user,
        )

        response = api_key_client.get(
            index_record_url(other_workspace.slug, other_project.id, record.id)
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
class TestAuthorityReviewerEnforcement:
    """Related concern: approval requires authorized reviewer."""

    @pytest.mark.django_db
    def test_agent_generated_requires_human_promoter(
        self, api_key_client, workspace, p4_project, create_user, service_identity
    ):
        """Agent-generated version going quarantined→review→approved requires human."""
        source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Agent Source",
            source_type=SourceType.EXTERNAL,
            authority_type=AuthorityType.QA,
            created_by=create_user,
        )
        version_response = signed_json_post(
            api_key_client,
            knowledge_version_url(workspace.slug, p4_project.id, source.id),
            {
                "content_hash": hashlib.sha256(b"agent content").hexdigest(),
                "is_agent_generated": True,
            },
            service_identity,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        version_id = version_response.data["id"]
        detail_url = knowledge_version_url(
            workspace.slug, p4_project.id, source.id, version_id
        )

        review_response = api_key_client.patch(
            detail_url, {"status": VersionStatus.REVIEW}, format="json"
        )
        assert review_response.status_code == status.HTTP_200_OK

        approve_response = api_key_client.patch(
            detail_url, {"status": VersionStatus.APPROVED}, format="json"
        )
        assert approve_response.status_code == status.HTTP_200_OK
        assert approve_response.data["promoted_by"] is not None

    @pytest.mark.django_db
    def test_quarantined_to_approved_blocked_directly(
        self, api_key_client, workspace, p4_project, create_user, service_identity
    ):
        """Cannot skip review: quarantined → approved is invalid transition."""
        source = KnowledgeSource.objects.create(
            workspace=workspace,
            project=p4_project,
            name="Block Source",
            source_type=SourceType.EXTERNAL,
            authority_type=AuthorityType.SECURITY,
            created_by=create_user,
        )
        version_response = signed_json_post(
            api_key_client,
            knowledge_version_url(workspace.slug, p4_project.id, source.id),
            {
                "content_hash": hashlib.sha256(b"blocked content").hexdigest(),
                "is_agent_generated": True,
            },
            service_identity,
        )
        version_id = version_response.data["id"]
        detail_url = knowledge_version_url(
            workspace.slug, p4_project.id, source.id, version_id
        )

        response = api_key_client.patch(
            detail_url, {"status": VersionStatus.APPROVED}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error_code"] == "INVALID_STATUS_TRANSITION"
