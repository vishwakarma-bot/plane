# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.utils import timezone
from rest_framework import status
from uuid import uuid4

from plane.agent_infra.models import AgentAssignment, AssignmentStatus, IdempotencyRecord
from plane.db.models import Issue, Project, ProjectMember, State


def assignment_url(workspace_slug, project_id, assignment_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-assignments/"
    return f"{base}{assignment_id}/" if assignment_id else base


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
