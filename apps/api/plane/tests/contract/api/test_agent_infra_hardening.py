# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.utils import timezone
from rest_framework import status
from uuid import uuid4

from plane.agent_infra.models import AgentAssignment, AgentRun, AuthorizingReview, ReviewDisposition
from plane.db.models import Issue, Project, ProjectMember, State, User


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


def review_disposition_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/review-dispositions/"
    )


def _create_enabled_project(workspace, owner, identifier):
    project = Project.objects.create(
        name=f"Project {identifier}",
        identifier=identifier,
        workspace=workspace,
        created_by=owner,
        is_agent_infra_enabled=True,
    )
    ProjectMember.objects.create(
        project=project,
        member=owner,
        role=20,
        is_active=True,
    )
    return project


def _create_issue(workspace, project, owner):
    state = State.objects.create(
        name="Todo",
        project=project,
        workspace=workspace,
        group="backlog",
        default=True,
    )
    return Issue.objects.create(
        name=f"Work Item {project.identifier}",
        workspace=workspace,
        project=project,
        state=state,
        created_by=owner,
    )


def _create_assignment(workspace, project, issue, owner):
    return AgentAssignment.objects.create(
        workspace=workspace,
        project=project,
        work_item=issue,
        agent_ref="agent/hardening-001",
        assignment_type="development",
        created_by=owner,
    )


def _create_run(workspace, project, assignment, owner):
    return AgentRun.objects.create(
        workspace=workspace,
        project=project,
        assignment=assignment,
        agent_ref="agent/hardening-001",
        model_used="gpt-4o",
        outcome="success",
        started_at=timezone.now(),
        correlation_id=f"corr-{uuid4().hex[:8]}",
        created_by=owner,
    )


def _create_authorizing_review(agent_run, owner):
    return AuthorizingReview.objects.create(
        run=agent_run,
        reviewer_agent_ref="agent/reviewer-001",
        reviewer_model="claude-3-opus",
        verdict="accepted",
        reason="Output meets acceptance criteria.",
        reviewed_at=timezone.now(),
        created_by=owner,
    )


@pytest.mark.contract
class TestAgentInfraHardening:
    @pytest.mark.django_db
    def test_assignment_work_item_must_belong_to_url_project(
        self, api_key_client, workspace, create_user
    ):
        project_a = _create_enabled_project(workspace, create_user, "PRJA")
        project_b = _create_enabled_project(workspace, create_user, "PRJB")
        issue_in_a = _create_issue(workspace, project_a, create_user)

        payload = {
            "work_item": str(issue_in_a.id),
            "agent_ref": "agent/hardening-001",
            "assignment_type": "development",
        }
        response = api_key_client.post(
            assignment_url(workspace.slug, project_b.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert AgentAssignment.objects.filter(project=project_b).count() == 0

    @pytest.mark.django_db
    def test_disposition_reviewer_is_bound_to_authenticated_user(
        self, api_key_client, workspace, create_user
    ):
        project = _create_enabled_project(workspace, create_user, "REV")
        issue = _create_issue(workspace, project, create_user)
        assignment = _create_assignment(workspace, project, issue, create_user)
        agent_run = _create_run(workspace, project, assignment, create_user)
        _create_authorizing_review(agent_run, create_user)

        unique_id = uuid4().hex[:8]
        other_user = User.objects.create(
            email=f"other-reviewer-{unique_id}@plane.so",
            username=f"other_reviewer_{unique_id}",
            first_name="Other",
            last_name="Reviewer",
        )
        other_user.set_password("test-password")
        other_user.save()

        payload = {
            "reviewer": str(other_user.id),
            "disposition": "approved",
            "reason": "Attempted impersonation.",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = api_key_client.post(
            review_disposition_url(workspace.slug, project.id, agent_run.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        disposition = ReviewDisposition.objects.get(run=agent_run)
        assert disposition.reviewer_id == create_user.id
        assert disposition.reviewer_id != other_user.id
        assert str(response.data["reviewer"]) == str(create_user.id)

    @pytest.mark.django_db
    def test_agent_run_is_immutable_after_creation(
        self, api_key_client, workspace, create_user
    ):
        project = _create_enabled_project(workspace, create_user, "IMM")
        issue = _create_issue(workspace, project, create_user)
        assignment = _create_assignment(workspace, project, issue, create_user)
        agent_run = _create_run(workspace, project, assignment, create_user)

        detail_url = run_url(workspace.slug, project.id, agent_run.id)
        patch_response = api_key_client.patch(
            detail_url,
            {"outcome": "failed"},
            format="json",
        )
        delete_response = api_key_client.delete(detail_url)

        assert patch_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert delete_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert AgentRun.objects.filter(pk=agent_run.id).exists()

    @pytest.mark.django_db
    def test_disposition_requires_authorizing_review(
        self, api_key_client, workspace, create_user
    ):
        project = _create_enabled_project(workspace, create_user, "REQ")
        issue = _create_issue(workspace, project, create_user)
        assignment = _create_assignment(workspace, project, issue, create_user)
        agent_run = _create_run(workspace, project, assignment, create_user)

        payload = {
            "disposition": "approved",
            "reason": "No authorizing review yet.",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = api_key_client.post(
            review_disposition_url(workspace.slug, project.id, agent_run.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "REVIEW_REQUIRED"
        assert ReviewDisposition.objects.count() == 0

    @pytest.mark.django_db
    def test_cross_project_assignment_fk_injection(
        self, api_key_client, workspace, create_user
    ):
        project_a = _create_enabled_project(workspace, create_user, "RUNA")
        project_b = _create_enabled_project(workspace, create_user, "RUNB")
        issue = _create_issue(workspace, project_a, create_user)
        assignment = _create_assignment(workspace, project_a, issue, create_user)

        payload = {
            "assignment": str(assignment.id),
            "agent_ref": "agent/hardening-001",
            "model_used": "gpt-4o",
            "outcome": "success",
            "started_at": timezone.now().isoformat(),
            "correlation_id": "corr-cross-project",
        }
        response = api_key_client.post(
            run_url(workspace.slug, project_b.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert AgentRun.objects.filter(project=project_b).count() == 0
