# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueRelation, Project, ProjectMember, State


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(name="Relations", identifier="RL", workspace=workspace)
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def state(db, workspace, project):
    return State.objects.create(name="Todo", group="backlog", workspace=workspace, project=project)


@pytest.fixture
def issues(db, workspace, project, state):
    return [
        Issue.objects.create(name=name, workspace=workspace, project=project, state=state)
        for name in ["First", "Second"]
    ]


def relation_url(workspace, project, issue):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/relations/"


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkItemRelationAPI:
    def test_create_list_and_delete_relation(self, api_key_client, workspace, project, issues, monkeypatch):
        monkeypatch.setattr("plane.api.views.issue.issue_activity.delay", lambda **kwargs: None)
        first, second = issues
        url = relation_url(workspace, project, first)

        response = api_key_client.post(
            url,
            {"relation_type": "blocked_by", "issues": [str(second.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert IssueRelation.objects.count() == 1

        response = api_key_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["blocked_by"] == [{"project_id": str(project.id), "issue_id": str(second.id)}]

        response = api_key_client.delete(url, {"related_issue": str(second.id)}, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueRelation.objects.exists()

    def test_anchor_item_must_belong_to_url_project(self, api_key_client, workspace, project, state, create_user):
        other_project = Project.objects.create(name="Other", identifier="OR", workspace=workspace)
        ProjectMember.objects.create(project=other_project, member=create_user, role=20, is_active=True)
        other_state = State.objects.create(
            name="Other todo", group="backlog", workspace=workspace, project=other_project
        )
        other_issue = Issue.objects.create(
            name="Other issue", workspace=workspace, project=other_project, state=other_state
        )

        response = api_key_client.get(relation_url(workspace, project, other_issue))
        assert response.status_code == status.HTTP_404_NOT_FOUND
