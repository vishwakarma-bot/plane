# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Page, Project, ProjectMember, ProjectPage


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(name="Pages", identifier="PG", workspace=workspace)
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


def page_list_url(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/pages/"


def page_detail_url(workspace, project, page):
    return f"{page_list_url(workspace, project)}{page.id}/"


@pytest.mark.contract
@pytest.mark.django_db
class TestPageAPI:
    def test_page_lifecycle(self, api_key_client, workspace, project, create_user):
        response = api_key_client.post(
            page_list_url(workspace, project),
            {"name": "QA rules", "description_html": "<p>Initial rules</p>"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        page = Page.objects.get(pk=response.data["id"])
        assert page.owned_by == create_user
        assert ProjectPage.objects.filter(page=page, project=project, deleted_at__isnull=True).exists()

        response = api_key_client.get(page_list_url(workspace, project))
        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.data["results"]] == [page.id]

        response = api_key_client.patch(
            page_detail_url(workspace, project, page),
            {"name": "QA rules v2"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "QA rules v2"

        response = api_key_client.patch(
            f"{page_detail_url(workspace, project, page)}archive/",
            {"archived": True},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["archived_at"] is not None

        response = api_key_client.delete(page_detail_url(workspace, project, page))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Page.objects.filter(pk=page.id).exists()

    def test_html_is_sanitized(self, api_key_client, workspace, project):
        response = api_key_client.post(
            page_list_url(workspace, project),
            {"name": "Unsafe", "description_html": '<p onclick="alert(1)">Rules</p><script>alert(1)</script>'},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "<script" not in response.data["description_html"]
        assert "onclick" not in response.data["description_html"]

    def test_project_in_url_scopes_page(self, api_key_client, workspace, project, create_user):
        other_project = Project.objects.create(name="Other", identifier="OT", workspace=workspace)
        ProjectMember.objects.create(project=other_project, member=create_user, role=20, is_active=True)
        page = Page.objects.create(name="Other page", workspace=workspace, owned_by=create_user)
        ProjectPage.objects.create(workspace=workspace, project=other_project, page=page)

        response = api_key_client.get(page_detail_url(workspace, project, page))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_requires_archive(self, api_key_client, workspace, project, create_user):
        page = Page.objects.create(name="Active page", workspace=workspace, owned_by=create_user)
        ProjectPage.objects.create(workspace=workspace, project=project, page=page)

        response = api_key_client.delete(page_detail_url(workspace, project, page))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Page.objects.filter(pk=page.id).exists()
