# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import pytest
from rest_framework import status
from uuid import uuid4

from plane.agent_infra.models import (
    AuthorityType,
    KnowledgeSource,
    KnowledgeVersion,
    SourceType,
    VersionStatus,
)
from plane.db.models import Project, ProjectMember, Workspace, WorkspaceMember
from plane.tests.helpers.agent_infra_auth import signed_json_post


def knowledge_source_url(workspace_slug, project_id, source_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/knowledge-sources/"
    return f"{base}{source_id}/" if source_id else base


def knowledge_version_url(workspace_slug, project_id, source_id, version_id=None):
    base = (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"knowledge-sources/{source_id}/versions/"
    )
    return f"{base}{version_id}/" if version_id else base


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


def _create_source(api_key_client, workspace, project, payload=None):
    payload = payload or {
        "name": "Isolation Knowledge Source",
        "source_type": SourceType.PLANE,
        "authority_type": AuthorityType.ARCHITECTURE,
        "url": "https://example.com/knowledge",
    }
    response = api_key_client.post(
        knowledge_source_url(workspace.slug, project.id),
        payload,
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


@pytest.mark.contract
class TestKnowledgeIsolation:
    @pytest.mark.django_db
    def test_cross_workspace_knowledge_source_denied(
        self, api_key_client, workspace, create_user
    ):
        unique_id = uuid4().hex[:8]
        other_workspace = Workspace.objects.create(
            name="Other Workspace",
            owner=create_user,
            slug=f"other-knowledge-{unique_id}",
        )
        WorkspaceMember.objects.create(workspace=other_workspace, member=create_user, role=20)

        project_a = _create_enabled_project(workspace, create_user, "KWA")
        project_b = _create_enabled_project(other_workspace, create_user, "KWB")

        created = _create_source(api_key_client, workspace, project_a)

        response = api_key_client.get(
            knowledge_source_url(other_workspace.slug, project_b.id, created["id"])
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_cross_project_knowledge_source_denied(
        self, api_key_client, workspace, create_user
    ):
        project_a = _create_enabled_project(workspace, create_user, "KPA")
        project_b = _create_enabled_project(workspace, create_user, "KPB")

        created = _create_source(api_key_client, workspace, project_a)

        response = api_key_client.get(
            knowledge_source_url(workspace.slug, project_b.id, created["id"])
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_knowledge_deletion_audit(self, api_key_client, workspace, create_user):
        project = _create_enabled_project(workspace, create_user, "KDL")
        created = _create_source(api_key_client, workspace, project)

        response = api_key_client.delete(
            knowledge_source_url(workspace.slug, project.id, created["id"])
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        source = KnowledgeSource.all_objects.get(pk=created["id"])
        assert source.is_retired is True
        assert source.retired_at is not None
        assert source.deleted_at is None

        list_response = api_key_client.get(knowledge_source_url(workspace.slug, project.id))
        assert list_response.status_code == status.HTTP_200_OK
        retired_in_list = [
            item for item in list_response.data["results"] if item["id"] == created["id"]
        ]
        assert len(retired_in_list) == 1
        assert retired_in_list[0]["is_retired"] is True

    @pytest.mark.django_db
    def test_source_retirement_verification(self, api_key_client, workspace, create_user):
        project = _create_enabled_project(workspace, create_user, "KRT")
        created = _create_source(api_key_client, workspace, project)

        response = api_key_client.delete(
            knowledge_source_url(workspace.slug, project.id, created["id"])
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        source = KnowledgeSource.objects.get(pk=created["id"])
        assert source.is_retired is True
        assert source.retired_at is not None

        detail_response = api_key_client.get(
            knowledge_source_url(workspace.slug, project.id, created["id"])
        )
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["is_retired"] is True

        list_response = api_key_client.get(knowledge_source_url(workspace.slug, project.id))
        assert list_response.status_code == status.HTTP_200_OK
        # Gate P4 expects retired sources to remain visible in list with retired status.
        retired_in_list = [
            item for item in list_response.data["results"] if item["id"] == created["id"]
        ]
        assert len(retired_in_list) == 1
        assert retired_in_list[0]["is_retired"] is True

    @pytest.mark.django_db
    def test_agent_generated_quarantine_enforcement(
        self, api_key_client, workspace, create_user, service_identity
    ):
        project = _create_enabled_project(workspace, create_user, "KGQ")
        source = _create_source(api_key_client, workspace, project)

        create_response = signed_json_post(
            api_key_client,
            knowledge_version_url(workspace.slug, project.id, source["id"]),
            {
                "content_hash": hashlib.sha256(b"agent generated").hexdigest(),
                "is_agent_generated": True,
            },
            service_identity,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        assert create_response.data["status"] == VersionStatus.QUARANTINED

        detail_url = knowledge_version_url(
            workspace.slug,
            project.id,
            source["id"],
            create_response.data["id"],
        )
        patch_response = api_key_client.patch(
            detail_url,
            {"status": VersionStatus.APPROVED},
            format="json",
        )

        assert patch_response.status_code == status.HTTP_409_CONFLICT
        assert patch_response.data["error_code"] == "INVALID_STATUS_TRANSITION"

    @pytest.mark.django_db
    def test_quarantined_to_approved_requires_review_step(
        self, api_key_client, workspace, create_user, service_identity
    ):
        project = _create_enabled_project(workspace, create_user, "KQR")
        source = _create_source(api_key_client, workspace, project)

        version_response = signed_json_post(
            api_key_client,
            knowledge_version_url(workspace.slug, project.id, source["id"]),
            {
                "content_hash": hashlib.sha256(b"review path").hexdigest(),
                "is_agent_generated": True,
            },
            service_identity,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        assert version_response.data["status"] == VersionStatus.QUARANTINED

        detail_url = knowledge_version_url(
            workspace.slug,
            project.id,
            source["id"],
            version_response.data["id"],
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

        version = KnowledgeVersion.objects.get(pk=version_response.data["id"])
        assert version.promoted_by_id is not None
        assert version.promoted_at is not None
