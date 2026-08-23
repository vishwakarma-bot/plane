# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status
from uuid import uuid4

from plane.agent_infra.models import AgentAssignment
from plane.db.models import Issue, Project, ProjectMember, State, User, Workspace, WorkspaceMember


def assignment_url(workspace_slug, project_id, assignment_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-assignments/"
    return f"{base}{assignment_id}/" if assignment_id else base


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


def _create_assignment(workspace, project, owner):
    state = State.objects.create(
        name="Todo",
        project=project,
        workspace=workspace,
        group="backlog",
        default=True,
    )
    issue = Issue.objects.create(
        name="Isolation Work Item",
        workspace=workspace,
        project=project,
        state=state,
        created_by=owner,
    )
    return AgentAssignment.objects.create(
        workspace=workspace,
        project=project,
        work_item=issue,
        agent_ref="agent/isolation-001",
        assignment_type="development",
        created_by=owner,
    )


@pytest.mark.contract
class TestAgentInfraIsolation:
    @pytest.mark.django_db
    def test_cross_workspace_access_denied(self, api_key_client, workspace, create_user):
        unique_id = uuid4().hex[:8]
        other_user = User.objects.create(
            email=f"other-{unique_id}@plane.so",
            username=f"other_{unique_id}",
            first_name="Other",
            last_name="User",
        )
        other_user.set_password("test-password")
        other_user.save()

        other_workspace = Workspace.objects.create(
            name="Other Workspace",
            owner=other_user,
            slug=f"other-workspace-{unique_id}",
        )
        WorkspaceMember.objects.create(workspace=other_workspace, member=other_user, role=20)

        other_project = _create_enabled_project(other_workspace, other_user, "OTH")
        _create_assignment(other_workspace, other_project, other_user)

        url = assignment_url(other_workspace.slug, other_project.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_cross_project_access_denied(self, api_key_client, workspace, create_user):
        project_a = _create_enabled_project(workspace, create_user, "PRJA")
        project_b = _create_enabled_project(workspace, create_user, "PRJB")

        ProjectMember.objects.filter(project=project_b, member=create_user).delete()
        _create_assignment(workspace, project_b, create_user)

        url = assignment_url(workspace.slug, project_b.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert AgentAssignment.objects.filter(project=project_a).count() == 0

    @pytest.mark.django_db
    def test_unauthenticated_access_denied(self, api_client, workspace, create_user):
        project = _create_enabled_project(workspace, create_user, "UNA")
        url = assignment_url(workspace.slug, project.id)

        response = api_client.get(url)

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(self, api_key_client, workspace, create_user):
        project = Project.objects.create(
            name="Disabled Agent Infra Project",
            identifier="DIS",
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

        url = assignment_url(workspace.slug, project.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
