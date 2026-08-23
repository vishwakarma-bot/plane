# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.utils import timezone
from rest_framework import status
from uuid import uuid4

from plane.agent_infra.models import AgentAssignment, AssignmentStatus, IdempotencyRecord
from plane.db.models import Issue, Project, ProjectMember, State, Workspace
from plane.tests.helpers.agent_infra_auth import create_service_identity, signed_json_post


def response_payload(response):
    if hasattr(response, "data"):
        return response.data
    return response.json()


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


@pytest.fixture
def agent_infra_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Agent Infra P3 Project",
        identifier="AIP3",
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
        name="P3 Work Item",
        workspace=workspace,
        project=agent_infra_project,
        state=state,
        created_by=create_user,
    )


@pytest.fixture
def assignment_payload(issue):
    return {
        "work_item": str(issue.id),
        "agent_ref": "agent/p3-001",
        "assignment_type": "development",
    }


@pytest.mark.contract
class TestServiceIdentityMiddlewarePassthrough:
    @pytest.mark.django_db
    def test_request_without_service_id_header_passes_through(
        self, api_key_client, workspace, agent_infra_project
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    @pytest.mark.django_db
    def test_partial_service_identity_headers_do_not_block_api_key_requests(
        self, api_key_client, workspace, agent_infra_project
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        response = api_key_client.get(
            url,
            HTTP_X_SIGNATURE="deadbeef",
            HTTP_X_TIMESTAMP=timezone.now().isoformat(),
        )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.contract
class TestServiceIdentityEnforcement:
    @pytest.mark.django_db
    def test_callback_endpoint_rejects_missing_service_identity(
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
            "agent_ref": "agent/p3-001",
            "model_used": "gpt-4o",
            "outcome": "success",
            "started_at": timezone.now().isoformat(),
            "correlation_id": "corr-missing-identity",
        }

        response = api_key_client.post(
            run_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response_payload(response)["error_code"] == "SERVICE_IDENTITY_REQUIRED"

    @pytest.mark.django_db
    def test_callback_endpoint_rejects_wrong_workspace(
        self, api_key_client, workspace, agent_infra_project, assignment_payload, create_user
    ):
        other_workspace = Workspace.objects.create(
            name="Other Workspace",
            slug="other-workspace",
            owner=create_user,
        )
        other_identity = create_service_identity(
            other_workspace,
            service_id="other-workspace-service",
            permissions=["report_runs"],
        )

        assignment_response = api_key_client.post(
            assignment_url(workspace.slug, agent_infra_project.id),
            assignment_payload,
            format="json",
        )
        assignment_id = assignment_response.data["id"]
        payload = {
            "assignment": assignment_id,
            "agent_ref": "agent/p3-001",
            "model_used": "gpt-4o",
            "outcome": "success",
            "started_at": timezone.now().isoformat(),
            "correlation_id": "corr-wrong-workspace",
        }

        response = signed_json_post(
            api_key_client,
            run_url(workspace.slug, agent_infra_project.id),
            payload,
            other_identity,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response_payload(response)["error_code"] == "PERMISSION_DENIED"

    @pytest.mark.django_db
    def test_callback_endpoint_rejects_missing_permission(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        identity = create_service_identity(
            workspace,
            service_id="runs-only-service",
            permissions=["report_runs"],
        )
        assignment_response = api_key_client.post(
            assignment_url(workspace.slug, agent_infra_project.id),
            assignment_payload,
            format="json",
        )
        assignment_id = assignment_response.data["id"]

        run_payload = {
            "assignment": assignment_id,
            "agent_ref": "agent/p3-001",
            "model_used": "gpt-4o",
            "outcome": "success",
            "started_at": timezone.now().isoformat(),
            "correlation_id": "corr-run",
        }
        run_response = signed_json_post(
            api_key_client,
            run_url(workspace.slug, agent_infra_project.id),
            run_payload,
            identity,
        )
        assert run_response.status_code == status.HTTP_201_CREATED

        review_payload = {
            "reviewer_agent_ref": "agent/reviewer-001",
            "reviewer_model": "claude-3-opus",
            "verdict": "accepted",
            "reason": "Output meets acceptance criteria.",
            "reviewed_at": timezone.now().isoformat(),
        }
        review_response = signed_json_post(
            api_key_client,
            authorizing_review_url(workspace.slug, agent_infra_project.id, run_response.data["id"]),
            review_payload,
            identity,
        )

        assert review_response.status_code == status.HTTP_403_FORBIDDEN
        assert response_payload(review_response)["error_code"] == "PERMISSION_DENIED"


@pytest.mark.contract
class TestIdempotentCallback:
    @pytest.mark.django_db
    def test_idempotent_post_returns_cached_response_on_replay(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        idempotency_key = str(uuid4())

        first_response = api_key_client.post(
            url,
            assignment_payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )
        second_response = api_key_client.post(
            url,
            assignment_payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_201_CREATED
        assert second_response.data == first_response.data
        assert AgentAssignment.objects.count() == 1
        assert IdempotencyRecord.objects.filter(idempotency_key=idempotency_key).count() == 1

    @pytest.mark.django_db
    def test_idempotency_rejects_different_body_reuse(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        idempotency_key = str(uuid4())

        first_response = api_key_client.post(
            url,
            assignment_payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )
        second_payload = {**assignment_payload, "agent_ref": "agent/p3-002"}
        second_response = api_key_client.post(
            url,
            second_payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response_payload(second_response)["error_code"] == "IDEMPOTENCY_KEY_REUSED"
        assert AgentAssignment.objects.count() == 1

    @pytest.mark.django_db
    def test_idempotency_rejects_cross_endpoint_reuse(
        self, api_key_client, workspace, agent_infra_project, assignment_payload, service_identity
    ):
        assignment_url_value = assignment_url(workspace.slug, agent_infra_project.id)
        idempotency_key = str(uuid4())

        assignment_response = api_key_client.post(
            assignment_url_value,
            assignment_payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )
        assert assignment_response.status_code == status.HTTP_201_CREATED

        run_payload = {
            "assignment": assignment_response.data["id"],
            "agent_ref": "agent/p3-001",
            "model_used": "gpt-4o",
            "outcome": "success",
            "started_at": timezone.now().isoformat(),
            "correlation_id": "corr-cross-endpoint",
        }
        run_response = signed_json_post(
            api_key_client,
            run_url(workspace.slug, agent_infra_project.id),
            run_payload,
            service_identity,
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )

        assert run_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response_payload(run_response)["error_code"] == "IDEMPOTENCY_KEY_REUSED"

    @pytest.mark.django_db
    def test_idempotency_rejects_cross_tenant_reuse(
        self, api_key_client, workspace, agent_infra_project, assignment_payload, create_user
    ):
        other_workspace = Workspace.objects.create(
            name="Tenant B",
            slug="tenant-b",
            owner=create_user,
        )
        other_project = Project.objects.create(
            name="Tenant B Project",
            identifier="TBP",
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
        other_state = State.objects.create(
            name="Todo",
            project=other_project,
            workspace=other_workspace,
            group="backlog",
            default=True,
        )
        other_issue = Issue.objects.create(
            name="Tenant B Work Item",
            workspace=other_workspace,
            project=other_project,
            state=other_state,
            created_by=create_user,
        )
        other_payload = {
            "work_item": str(other_issue.id),
            "agent_ref": "agent/p3-001",
            "assignment_type": "development",
        }
        idempotency_key = str(uuid4())

        first_response = api_key_client.post(
            assignment_url(workspace.slug, agent_infra_project.id),
            assignment_payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )
        second_response = api_key_client.post(
            assignment_url(other_workspace.slug, other_project.id),
            other_payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=idempotency_key,
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response_payload(second_response)["error_code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.contract
class TestClaimAssignment:
    @pytest.mark.django_db
    def test_claim_assignment_returns_409_on_invalid_transition(
        self, api_key_client, workspace, agent_infra_project, assignment_payload
    ):
        create_url = assignment_url(workspace.slug, agent_infra_project.id)
        create_response = api_key_client.post(create_url, assignment_payload, format="json")
        assignment_id = create_response.data["id"]

        AgentAssignment.objects.filter(pk=assignment_id).update(status=AssignmentStatus.CANCELLED)

        detail_url = assignment_url(workspace.slug, agent_infra_project.id, assignment_id)
        response = api_key_client.patch(detail_url, {"status": "running"}, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error_code"] == "INVALID_STATUS_TRANSITION"
        assert "correlation_id" in response.data
        assert AgentAssignment.objects.get(pk=assignment_id).status == AssignmentStatus.CANCELLED


@pytest.mark.contract
class TestAssignmentStatusFilter:
    @pytest.mark.django_db
    def test_list_assignments_filters_by_status_query_param(
        self, api_key_client, workspace, agent_infra_project, issue, create_user
    ):
        pending = AgentAssignment.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            work_item=issue,
            agent_ref="agent/pending",
            assignment_type="development",
            status=AssignmentStatus.PENDING,
            created_by=create_user,
        )
        AgentAssignment.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            work_item=issue,
            agent_ref="agent/running",
            assignment_type="development",
            status=AssignmentStatus.RUNNING,
            created_by=create_user,
        )

        url = assignment_url(workspace.slug, agent_infra_project.id)
        response = api_key_client.get(url, {"status": "pending"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert str(response.data["results"][0]["id"]) == str(pending.id)
        assert response.data["results"][0]["status"] == AssignmentStatus.PENDING


@pytest.mark.contract
class TestProtocolErrorFormat:
    @pytest.mark.django_db
    def test_validation_errors_use_protocol_format(
        self, api_key_client, workspace, agent_infra_project, issue
    ):
        url = assignment_url(workspace.slug, agent_infra_project.id)
        payload = {
            "work_item": str(issue.id),
            "agent_ref": "agent/p3-001",
            "assignment_type": "invalid-type",
        }
        response = api_key_client.post(
            url,
            payload,
            format="json",
            HTTP_X_REQUEST_ID="corr-validation-test",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert "message" in response.data
        assert response.data["correlation_id"] == "corr-validation-test"
        assert response.data["retry_after"] is None
