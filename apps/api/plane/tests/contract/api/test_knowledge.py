# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import pytest
from django.utils import timezone
from rest_framework import status
from uuid import uuid4

from plane.agent_infra.models import (
    AgentAssignment,
    AgentRun,
    AssignmentType,
    ContextManifest,
    KnowledgeSource,
    KnowledgeVersion,
    RunOutcome,
    SourceType,
    AuthorityType,
    VersionStatus,
)
from plane.db.models import Issue, Project, ProjectMember, State, Workspace
from plane.tests.helpers.agent_infra_auth import create_service_identity, signed_json_post


def knowledge_source_url(workspace_slug, project_id, source_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/knowledge-sources/"
    return f"{base}{source_id}/" if source_id else base


def knowledge_version_url(workspace_slug, project_id, source_id, version_id=None):
    base = (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"knowledge-sources/{source_id}/versions/"
    )
    return f"{base}{version_id}/" if version_id else base


def context_manifest_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/context-manifests/"
    )


@pytest.fixture
def agent_infra_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Knowledge P4 Project",
        identifier="KNP4",
        workspace=workspace,
        created_by=create_user,
        is_agent_infra_enabled=True,
    )
    ProjectMember.objects.create(
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    return project


@pytest.fixture
def state(db, workspace, agent_infra_project):
    return State.objects.create(
        name="Todo",
        project=agent_infra_project,
        workspace=workspace,
        group="backlog",
        default=True,
    )


@pytest.fixture
def issue(db, workspace, agent_infra_project, state, create_user):
    return Issue.objects.create(
        name="Knowledge Work Item",
        workspace=workspace,
        project=agent_infra_project,
        state=state,
        created_by=create_user,
    )


@pytest.fixture
def agent_run(db, workspace, agent_infra_project, issue, create_user):
    assignment = AgentAssignment.objects.create(
        workspace=workspace,
        project=agent_infra_project,
        work_item=issue,
        agent_ref="agent/knowledge-test",
        assignment_type=AssignmentType.DEVELOPMENT,
        created_by=create_user,
    )
    return AgentRun.objects.create(
        workspace=workspace,
        project=agent_infra_project,
        assignment=assignment,
        agent_ref="agent/knowledge-test",
        model_used="gpt-4o",
        outcome=RunOutcome.SUCCESS,
        started_at=timezone.now(),
        correlation_id="corr-knowledge-test",
        created_by=create_user,
    )


@pytest.fixture
def knowledge_source_payload():
    return {
        "name": "Architecture Decision Record",
        "source_type": SourceType.PLANE,
        "authority_type": AuthorityType.ARCHITECTURE,
        "url": "https://example.com/adr/001",
    }


@pytest.fixture
def knowledge_version_payload():
    return {
        "content_hash": hashlib.sha256(b"draft content").hexdigest(),
        "diff_summary": "Initial draft",
        "status": VersionStatus.DRAFT,
    }


def _create_source(api_key_client, workspace, project, payload):
    response = api_key_client.post(
        knowledge_source_url(workspace.slug, project.id),
        payload,
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


@pytest.mark.contract
class TestKnowledgeSourceAPI:
    @pytest.mark.django_db
    def test_create_knowledge_source(
        self, api_key_client, workspace, agent_infra_project, knowledge_source_payload
    ):
        response = api_key_client.post(
            knowledge_source_url(workspace.slug, agent_infra_project.id),
            knowledge_source_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == knowledge_source_payload["name"]
        assert response.data["source_type"] == SourceType.PLANE
        assert response.data["is_retired"] is False

    @pytest.mark.django_db
    def test_list_knowledge_sources(
        self, api_key_client, workspace, agent_infra_project, knowledge_source_payload
    ):
        _create_source(api_key_client, workspace, agent_infra_project, knowledge_source_payload)

        response = api_key_client.get(
            knowledge_source_url(workspace.slug, agent_infra_project.id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["name"] == knowledge_source_payload["name"]

    @pytest.mark.django_db
    def test_get_knowledge_source_detail(
        self, api_key_client, workspace, agent_infra_project, knowledge_source_payload
    ):
        created = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )

        response = api_key_client.get(
            knowledge_source_url(workspace.slug, agent_infra_project.id, created["id"])
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == created["id"]

    @pytest.mark.django_db
    def test_update_knowledge_source(
        self, api_key_client, workspace, agent_infra_project, knowledge_source_payload
    ):
        created = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )

        response = api_key_client.patch(
            knowledge_source_url(workspace.slug, agent_infra_project.id, created["id"]),
            {"name": "Updated ADR"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated ADR"

    @pytest.mark.django_db
    def test_retire_knowledge_source(
        self, api_key_client, workspace, agent_infra_project, knowledge_source_payload
    ):
        created = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )

        response = api_key_client.delete(
            knowledge_source_url(workspace.slug, agent_infra_project.id, created["id"])
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        source = KnowledgeSource.objects.get(pk=created["id"])
        assert source.is_retired is True
        assert source.retired_at is not None


@pytest.mark.contract
class TestKnowledgeVersionAPI:
    @pytest.mark.django_db
    def test_create_knowledge_version_draft(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        knowledge_source_payload,
        knowledge_version_payload,
    ):
        source = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )

        response = api_key_client.post(
            knowledge_version_url(workspace.slug, agent_infra_project.id, source["id"]),
            knowledge_version_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == VersionStatus.DRAFT
        assert response.data["version_number"] == 1
        assert response.data["is_agent_generated"] is False

    @pytest.mark.django_db
    def test_agent_generated_version_enters_quarantined(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        knowledge_source_payload,
        service_identity,
    ):
        source = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )
        payload = {
            "content_hash": hashlib.sha256(b"agent content").hexdigest(),
            "diff_summary": "Agent-discovered context",
            "is_agent_generated": True,
        }

        response = signed_json_post(
            api_key_client,
            knowledge_version_url(workspace.slug, agent_infra_project.id, source["id"]),
            payload,
            service_identity,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == VersionStatus.QUARANTINED
        assert response.data["is_agent_generated"] is True

    @pytest.mark.django_db
    def test_version_lifecycle_draft_to_approved(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        knowledge_source_payload,
        knowledge_version_payload,
    ):
        source = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )
        version_response = api_key_client.post(
            knowledge_version_url(workspace.slug, agent_infra_project.id, source["id"]),
            knowledge_version_payload,
            format="json",
        )
        version_id = version_response.data["id"]
        detail_url = knowledge_version_url(
            workspace.slug, agent_infra_project.id, source["id"], version_id
        )

        review_response = api_key_client.patch(
            detail_url,
            {"status": VersionStatus.REVIEW},
            format="json",
        )
        assert review_response.status_code == status.HTTP_200_OK
        assert review_response.data["status"] == VersionStatus.REVIEW

        approved_response = api_key_client.patch(
            detail_url,
            {"status": VersionStatus.APPROVED},
            format="json",
        )
        assert approved_response.status_code == status.HTTP_200_OK
        assert approved_response.data["status"] == VersionStatus.APPROVED
        assert approved_response.data["promoted_by"] is not None
        assert approved_response.data["promoted_at"] is not None

    @pytest.mark.django_db
    def test_invalid_version_transition_returns_409(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        knowledge_source_payload,
        knowledge_version_payload,
    ):
        source = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )
        version_response = api_key_client.post(
            knowledge_version_url(workspace.slug, agent_infra_project.id, source["id"]),
            knowledge_version_payload,
            format="json",
        )
        detail_url = knowledge_version_url(
            workspace.slug,
            agent_infra_project.id,
            source["id"],
            version_response.data["id"],
        )

        response = api_key_client.patch(
            detail_url,
            {"status": VersionStatus.APPROVED},
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error_code"] == "INVALID_STATUS_TRANSITION"

    @pytest.mark.django_db
    def test_quarantined_version_cannot_auto_promote(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        knowledge_source_payload,
        service_identity,
    ):
        source = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )
        version_response = signed_json_post(
            api_key_client,
            knowledge_version_url(workspace.slug, agent_infra_project.id, source["id"]),
            {
                "content_hash": hashlib.sha256(b"quarantined").hexdigest(),
                "is_agent_generated": True,
            },
            service_identity,
        )
        detail_url = knowledge_version_url(
            workspace.slug,
            agent_infra_project.id,
            source["id"],
            version_response.data["id"],
        )

        response = api_key_client.patch(
            detail_url,
            {"status": VersionStatus.APPROVED},
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error_code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.contract
class TestContextManifestAPI:
    @pytest.mark.django_db
    def test_create_context_manifest(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        knowledge_source_payload,
        knowledge_version_payload,
        service_identity,
    ):
        source = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )
        version_response = api_key_client.post(
            knowledge_version_url(workspace.slug, agent_infra_project.id, source["id"]),
            knowledge_version_payload,
            format="json",
        )

        response = signed_json_post(
            api_key_client,
            context_manifest_url(workspace.slug, agent_infra_project.id, agent_run.id),
            {"knowledge_version": version_response.data["id"]},
            service_identity,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert str(response.data["run"]) == str(agent_run.id)
        assert str(response.data["knowledge_version"]) == str(version_response.data["id"])
        assert ContextManifest.objects.filter(run=agent_run).count() == 1

    @pytest.mark.django_db
    def test_manifest_duplicate_returns_cached(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        knowledge_source_payload,
        knowledge_version_payload,
        service_identity,
    ):
        source = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )
        version_response = api_key_client.post(
            knowledge_version_url(workspace.slug, agent_infra_project.id, source["id"]),
            knowledge_version_payload,
            format="json",
        )
        url = context_manifest_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {"knowledge_version": version_response.data["id"]}
        idempotency_key = str(uuid4())

        first_response = signed_json_post(
            api_key_client,
            url,
            payload,
            service_identity,
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )
        second_response = signed_json_post(
            api_key_client,
            url,
            payload,
            service_identity,
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_201_CREATED
        assert second_response.data["id"] == first_response.data["id"]
        assert ContextManifest.objects.filter(run=agent_run).count() == 1


@pytest.mark.contract
class TestKnowledgeSecurity:
    @pytest.mark.django_db
    def test_cross_workspace_knowledge_denied(
        self, api_key_client, workspace, agent_infra_project, knowledge_source_payload, create_user
    ):
        other_workspace = Workspace.objects.create(
            name="Other Knowledge Workspace",
            slug="other-knowledge-workspace",
            owner=create_user,
        )
        other_project = Project.objects.create(
            name="Other Knowledge Project",
            identifier="OKP",
            workspace=other_workspace,
            created_by=create_user,
            is_agent_infra_enabled=True,
        )
        ProjectMember.objects.create(
            project=other_project,
            member=create_user,
            role=20,
            is_active=True,
        )

        created = _create_source(
            api_key_client, workspace, agent_infra_project, knowledge_source_payload
        )

        response = api_key_client.get(
            knowledge_source_url(other_workspace.slug, other_project.id, created["id"])
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(
        self, api_key_client, workspace, create_user, knowledge_source_payload
    ):
        project = Project.objects.create(
            name="Disabled Knowledge Project",
            identifier="DKP",
            workspace=workspace,
            created_by=create_user,
            is_agent_infra_enabled=False,
        )
        ProjectMember.objects.create(
            project=project,
            member=create_user,
            role=20,
            is_active=True,
        )

        response = api_key_client.get(
            knowledge_source_url(workspace.slug, project.id)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
