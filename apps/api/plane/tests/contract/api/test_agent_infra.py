# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.utils import timezone
from rest_framework import status

from plane.agent_infra.models import (
    AgentAssignment,
    AgentRun,
    ArtifactReference,
    AuthorizingReview,
    ReviewDisposition,
)
from plane.db.models import Issue, Project, ProjectMember, State


@pytest.fixture
def agent_infra_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Agent Infra Project",
        identifier="AIP",
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
        name="Agent Work Item",
        workspace=workspace,
        project=agent_infra_project,
        state=state,
        created_by=create_user,
    )


def assignment_url(workspace_slug, project_id, assignment_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-assignments/"
    return f"{base}{assignment_id}/" if assignment_id else base


def run_url(workspace_slug, project_id, run_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-runs/"
    return f"{base}{run_id}/" if run_id else base


def authorizing_review_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/authorizing-reviews/"
    )


def artifact_reference_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/artifact-references/"
    )


def review_disposition_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/review-dispositions/"
    )


@pytest.fixture
def assignment_payload(issue):
    return {
        "work_item": str(issue.id),
        "agent_ref": "agent/dev-001",
        "assignment_type": "development",
    }


@pytest.fixture
def agent_run(db, workspace, agent_infra_project, issue, create_user):
    assignment = AgentAssignment.objects.create(
        workspace=workspace,
        project=agent_infra_project,
        work_item=issue,
        agent_ref="agent/dev-001",
        assignment_type="development",
        created_by=create_user,
    )
    return AgentRun.objects.create(
        workspace=workspace,
        project=agent_infra_project,
        assignment=assignment,
        agent_ref="agent/dev-001",
        model_used="gpt-4o",
        outcome="success",
        started_at=timezone.now(),
        correlation_id="corr-001",
        created_by=create_user,
    )


@pytest.mark.contract
class TestAgentAssignment:
    @pytest.mark.django_db
    def test_list_assignments_returns_empty(
        self, api_key_client, workspace, agent_infra_project
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    @pytest.mark.django_db
    def test_create_assignment(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        response = api_key_client.post(url, assignment_payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["agent_ref"] == assignment_payload["agent_ref"]
        assert response.data["assignment_type"] == assignment_payload["assignment_type"]
        assert AgentAssignment.objects.count() == 1

    @pytest.mark.django_db
    def test_create_assignment_invalid_type(
        self, api_key_client, workspace, agent_infra_project, issue
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        payload = {
            "work_item": str(issue.id),
            "agent_ref": "agent/dev-001",
            "assignment_type": "invalid-type",
        }
        response = api_key_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert AgentAssignment.objects.count() == 0

    @pytest.mark.django_db
    def test_get_assignment_detail(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        create_url = assignment_url(workspace.slug, agent_infra_project.id)
        create_response = api_key_client.post(create_url, assignment_payload, format="json")
        assignment_id = create_response.data["id"]

        detail_url = assignment_url(workspace.slug, agent_infra_project.id, assignment_id)
        response = api_key_client.get(detail_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == assignment_id
        assert response.data["agent_ref"] == assignment_payload["agent_ref"]

    @pytest.mark.django_db
    def test_update_assignment_status(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        create_url = assignment_url(workspace.slug, agent_infra_project.id)
        create_response = api_key_client.post(create_url, assignment_payload, format="json")
        assignment_id = create_response.data["id"]

        detail_url = assignment_url(workspace.slug, agent_infra_project.id, assignment_id)
        response = api_key_client.patch(detail_url, {"status": "running"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "running"

    @pytest.mark.django_db
    def test_delete_assignment(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        create_url = assignment_url(workspace.slug, agent_infra_project.id)
        create_response = api_key_client.post(create_url, assignment_payload, format="json")
        assignment_id = create_response.data["id"]

        detail_url = assignment_url(workspace.slug, agent_infra_project.id, assignment_id)
        response = api_key_client.delete(detail_url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert AgentAssignment.objects.count() == 0


@pytest.mark.contract
class TestAgentRun:
    @pytest.mark.django_db
    def test_create_run(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        assignment_response = api_key_client.post(
            assignment_url(workspace.slug, agent_infra_project.id),
            assignment_payload,
            format="json",
        )
        assignment_id = assignment_response.data["id"]

        payload = {
            "assignment": assignment_id,
            "agent_ref": "agent/dev-001",
            "model_used": "gpt-4o",
            "outcome": "success",
            "started_at": timezone.now().isoformat(),
            "correlation_id": "corr-create-run",
        }
        response = api_key_client.post(
            run_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["assignment"] == assignment_id
        assert response.data["model_used"] == "gpt-4o"
        assert AgentRun.objects.count() == 1

    @pytest.mark.django_db
    def test_run_requires_assignment(
        self, api_key_client, workspace, agent_infra_project
    ):
        payload = {
            "agent_ref": "agent/dev-001",
            "model_used": "gpt-4o",
            "outcome": "success",
            "started_at": timezone.now().isoformat(),
            "correlation_id": "corr-no-assignment",
        }
        response = api_key_client.post(
            run_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert AgentRun.objects.count() == 0


@pytest.mark.contract
class TestAuthorizingReview:
    @pytest.mark.django_db
    def test_create_review(self, api_key_client, workspace, agent_infra_project, agent_run):
        payload = {
            "reviewer_agent_ref": "agent/reviewer-001",
            "reviewer_model": "claude-3-opus",
            "verdict": "accepted",
            "reason": "Output meets acceptance criteria.",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = api_key_client.post(
            authorizing_review_url(workspace.slug, agent_infra_project.id, agent_run.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["verdict"] == "accepted"
        assert AuthorizingReview.objects.count() == 1

    @pytest.mark.django_db
    def test_review_model_must_differ(
        self, api_key_client, workspace, agent_infra_project, agent_run
    ):
        payload = {
            "reviewer_agent_ref": "agent/reviewer-001",
            "reviewer_model": agent_run.model_used,
            "verdict": "accepted",
            "reason": "Same model should be rejected.",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = api_key_client.post(
            authorizing_review_url(workspace.slug, agent_infra_project.id, agent_run.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert AuthorizingReview.objects.count() == 0


@pytest.mark.contract
class TestArtifactReference:
    @pytest.mark.django_db
    def test_create_artifact_reference(
        self, api_key_client, workspace, agent_infra_project, agent_run
    ):
        payload = {
            "artifact_type": "log",
            "storage_ref": "s3://bucket/logs/run-001.log",
            "hash": "abc123",
            "classification": "internal",
        }
        response = api_key_client.post(
            artifact_reference_url(workspace.slug, agent_infra_project.id, agent_run.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["artifact_type"] == "log"
        assert ArtifactReference.objects.count() == 1

    @pytest.mark.django_db
    def test_list_artifacts_for_run(
        self, api_key_client, workspace, agent_infra_project, agent_run, create_user
    ):
        ArtifactReference.objects.create(
            run=agent_run,
            artifact_type="log",
            storage_ref="s3://bucket/logs/run-001.log",
            hash="abc123",
            classification="internal",
            created_by=create_user,
        )
        ArtifactReference.objects.create(
            run=agent_run,
            artifact_type="screenshot",
            storage_ref="s3://bucket/screens/run-001.png",
            hash="def456",
            classification="public",
            created_by=create_user,
        )

        response = api_key_client.get(
            artifact_reference_url(workspace.slug, agent_infra_project.id, agent_run.id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2
        artifact_types = {item["artifact_type"] for item in response.data["results"]}
        assert artifact_types == {"log", "screenshot"}


@pytest.mark.contract
class TestReviewDisposition:
    @pytest.mark.django_db
    def test_create_disposition(
        self, api_key_client, workspace, agent_infra_project, agent_run, create_user
    ):
        review_payload = {
            "reviewer_agent_ref": "agent/reviewer-001",
            "reviewer_model": "claude-3-opus",
            "verdict": "accepted",
            "reason": "Output meets acceptance criteria.",
            "reviewed_at": timezone.now().isoformat(),
        }
        review_response = api_key_client.post(
            authorizing_review_url(workspace.slug, agent_infra_project.id, agent_run.id),
            review_payload,
            format="json",
        )
        assert review_response.status_code == status.HTTP_201_CREATED

        payload = {
            "reviewer": str(create_user.id),
            "disposition": "approved",
            "reason": "Looks good to merge.",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = api_key_client.post(
            review_disposition_url(workspace.slug, agent_infra_project.id, agent_run.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["disposition"] == "approved"
        assert ReviewDisposition.objects.count() == 1

    @pytest.mark.django_db
    def test_disposition_is_optional(
        self, api_key_client, workspace, agent_infra_project, agent_run
    ):
        detail_url = run_url(workspace.slug, agent_infra_project.id, agent_run.id)
        response = api_key_client.get(detail_url)

        assert response.status_code == status.HTTP_200_OK
        assert ReviewDisposition.objects.filter(run=agent_run).count() == 0

        list_response = api_key_client.get(
            review_disposition_url(workspace.slug, agent_infra_project.id, agent_run.id)
        )
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data["results"] == []
