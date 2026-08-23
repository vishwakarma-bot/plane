# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib

import pytest
from rest_framework import status

from plane.agent_infra.models import (
    AutonomyLevel,
    CatalogEntityType,
    CatalogRevision,
    CatalogRevisionStatus,
    CompatibilityEntityType,
    CompatibilityRecord,
    DriftStatus,
    IntegrationType,
    ProjectAgentEnablement,
    RevisionStatus,
)
from plane.agent_infra.services.enablement import AgentEnablementService
from plane.agent_infra.services.routing import ModelRoutingService
from plane.agent_infra.services.versioning import CatalogVersioningService
from plane.db.models import Project, ProjectMember


def enablement_url(workspace_slug, project_id, enablement_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-enablements/"
    return f"{base}{enablement_id}/" if enablement_id else base


def routing_config_url(workspace_slug, project_id, config_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/model-routing-configs/"
    return f"{base}{config_id}/" if config_id else base


def environment_revision_url(workspace_slug, project_id, revision_id=None, drift_check=False):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/environment-revisions/"
    if revision_id and drift_check:
        return f"{base}{revision_id}/drift-check/"
    return f"{base}{revision_id}/" if revision_id else base


def integration_registration_url(workspace_slug, project_id, registration_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/integration-registrations/"
    return f"{base}{registration_id}/" if registration_id else base


def catalog_revision_url(workspace_slug, project_id, revision_id=None, action=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/catalog-revisions/"
    if revision_id and action:
        return f"{base}{revision_id}/{action}/"
    return f"{base}{revision_id}/" if revision_id else base


def compatibility_check_url(workspace_slug, project_id):
    return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/compatibility-checks/"


@pytest.fixture
def agent_infra_project(db, workspace, create_user):
    project = Project.objects.create(
        name="P5 Governance Project",
        identifier="P5GOV",
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


@pytest.mark.contract
class TestP5GovernanceAPI:
    @pytest.mark.django_db
    def test_create_agent_enablement(self, api_key_client, workspace, agent_infra_project):
        payload = {
            "agent_ref": "agent/dev-001",
            "enabled": True,
            "max_autonomy_level": AutonomyLevel.SUPERVISED,
            "allowed_assignment_types": ["development"],
            "delegation_permissions": ["review"],
        }
        response = api_key_client.post(
            enablement_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["agent_ref"] == "agent/dev-001"
        assert response.data["enabled"] is True

    @pytest.mark.django_db
    def test_list_agent_enablements(self, api_key_client, workspace, agent_infra_project):
        ProjectAgentEnablement.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            agent_ref="agent/list-test",
            enabled=True,
        )

        response = api_key_client.get(
            enablement_url(workspace.slug, agent_infra_project.id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    @pytest.mark.django_db
    def test_patch_agent_enablement(self, api_key_client, workspace, agent_infra_project):
        enablement = ProjectAgentEnablement.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            agent_ref="agent/patch-test",
            enabled=True,
        )

        response = api_key_client.patch(
            enablement_url(workspace.slug, agent_infra_project.id, enablement.id),
            {"enabled": False},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["enabled"] is False

    @pytest.mark.django_db
    def test_delete_agent_enablement(self, api_key_client, workspace, agent_infra_project):
        enablement = ProjectAgentEnablement.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            agent_ref="agent/delete-test",
            enabled=True,
        )

        response = api_key_client.delete(
            enablement_url(workspace.slug, agent_infra_project.id, enablement.id)
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ProjectAgentEnablement.objects.filter(pk=enablement.id).exists()

    @pytest.mark.django_db
    def test_enablement_service_blocks_disallowed_assignment_type(
        self, workspace, agent_infra_project
    ):
        ProjectAgentEnablement.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            agent_ref="agent/restricted",
            enabled=True,
            allowed_assignment_types=["review"],
        )

        allowed, message = AgentEnablementService.check_assignment_allowed(
            workspace.id,
            agent_infra_project.id,
            "agent/restricted",
            "development",
        )

        assert allowed is False
        assert "not allowed" in message

    @pytest.mark.django_db
    def test_create_model_routing_config(self, api_key_client, workspace, agent_infra_project):
        payload = {
            "model_ref": "model/gpt-4o",
            "routing_priority": 10,
            "budget_limit_usd": "100.00",
            "eligible_risk_classes": ["low"],
            "eligible_assignment_types": ["development"],
        }
        response = api_key_client.post(
            routing_config_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["model_ref"] == "model/gpt-4o"
        assert response.data["budget_used_usd"] == "0.00"

    @pytest.mark.django_db
    def test_list_model_routing_configs_ordered_by_priority(
        self, api_key_client, workspace, agent_infra_project
    ):
        from plane.agent_infra.models import ModelRoutingConfig

        ModelRoutingConfig.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            model_ref="model/slow",
            routing_priority=200,
        )
        ModelRoutingConfig.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            model_ref="model/fast",
            routing_priority=10,
        )

        response = api_key_client.get(
            routing_config_url(workspace.slug, agent_infra_project.id)
        )

        assert response.status_code == status.HTTP_200_OK
        refs = [item["model_ref"] for item in response.data["results"]]
        assert refs == ["model/fast", "model/slow"]

    @pytest.mark.django_db
    def test_routing_service_budget_check(self, workspace, agent_infra_project):
        from decimal import Decimal
        from plane.agent_infra.models import ModelRoutingConfig

        ModelRoutingConfig.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            model_ref="model/budgeted",
            budget_limit_usd=Decimal("10.00"),
            budget_used_usd=Decimal("9.00"),
        )

        allowed, message = ModelRoutingService.check_budget(
            workspace.id,
            agent_infra_project.id,
            "model/budgeted",
            Decimal("2.00"),
        )

        assert allowed is False
        assert "Budget exceeded" in message

    @pytest.mark.django_db
    def test_create_environment_revision(self, api_key_client, workspace, agent_infra_project):
        content_hash = hashlib.sha256(b"env snapshot").hexdigest()
        payload = {
            "environment_ref": "env/staging",
            "content_hash": content_hash,
            "snapshot": {"python": "3.12", "node": "20"},
        }
        response = api_key_client.post(
            environment_revision_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["revision_number"] == 1
        assert response.data["environment_ref"] == "env/staging"

    @pytest.mark.django_db
    def test_activate_environment_revision_supersedes_previous(
        self, api_key_client, workspace, agent_infra_project
    ):
        from plane.agent_infra.models import EnvironmentRevision

        rev1 = EnvironmentRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            environment_ref="env/prod",
            revision_number=1,
            content_hash=hashlib.sha256(b"v1").hexdigest(),
            snapshot={"version": 1},
            status=RevisionStatus.ACTIVE,
        )
        rev2 = EnvironmentRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            environment_ref="env/prod",
            revision_number=2,
            content_hash=hashlib.sha256(b"v2").hexdigest(),
            snapshot={"version": 2},
            status=RevisionStatus.DRAFT,
        )

        response = api_key_client.patch(
            environment_revision_url(workspace.slug, agent_infra_project.id, rev2.id),
            {"status": RevisionStatus.ACTIVE},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == RevisionStatus.ACTIVE
        rev1.refresh_from_db()
        assert rev1.status == RevisionStatus.SUPERSEDED

    @pytest.mark.django_db
    def test_environment_drift_check_in_sync(
        self, api_key_client, workspace, agent_infra_project
    ):
        from plane.agent_infra.models import EnvironmentRevision

        content_hash = hashlib.sha256(b"stable").hexdigest()
        revision = EnvironmentRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            environment_ref="env/stable",
            revision_number=1,
            content_hash=content_hash,
            snapshot={"key": "value"},
        )

        response = api_key_client.post(
            environment_revision_url(
                workspace.slug, agent_infra_project.id, revision.id, drift_check=True
            ),
            {"content_hash": content_hash},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["drift_status"] == DriftStatus.IN_SYNC

    @pytest.mark.django_db
    def test_environment_drift_check_drifted(
        self, api_key_client, workspace, agent_infra_project
    ):
        from plane.agent_infra.models import EnvironmentRevision

        revision = EnvironmentRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            environment_ref="env/drift",
            revision_number=1,
            content_hash=hashlib.sha256(b"expected").hexdigest(),
            snapshot={"key": "expected"},
        )

        response = api_key_client.post(
            environment_revision_url(
                workspace.slug, agent_infra_project.id, revision.id, drift_check=True
            ),
            {"content_hash": hashlib.sha256(b"actual").hexdigest()},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["drift_status"] == DriftStatus.DRIFTED
        assert response.data["drift_detail"]["actual_hash"] is not None

    @pytest.mark.django_db
    def test_create_integration_registration(
        self, api_key_client, workspace, agent_infra_project
    ):
        payload = {
            "integration_ref": "integration/mcp-github",
            "integration_type": IntegrationType.MCP,
            "server_identity": "github-mcp-server",
            "granted_agents": ["agent/dev-001"],
            "granted_scopes": ["repos:read"],
        }
        response = api_key_client.post(
            integration_registration_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["integration_ref"] == "integration/mcp-github"

    @pytest.mark.django_db
    def test_list_integration_registrations(
        self, api_key_client, workspace, agent_infra_project
    ):
        from plane.agent_infra.models import IntegrationRegistration

        IntegrationRegistration.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            integration_ref="integration/ci",
            integration_type=IntegrationType.GIT_CI,
        )

        response = api_key_client.get(
            integration_registration_url(workspace.slug, agent_infra_project.id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    @pytest.mark.django_db
    def test_create_catalog_revision(self, api_key_client, workspace, agent_infra_project):
        payload = {
            "entity_type": CatalogEntityType.AGENT,
            "entity_ref": "agent/catalog-001",
            "content_hash": hashlib.sha256(b"v1").hexdigest(),
            "content_snapshot": {"name": "Dev Agent", "skills": ["coding"]},
        }
        response = api_key_client.post(
            catalog_revision_url(workspace.slug, agent_infra_project.id),
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["revision_number"] == 1
        assert response.data["status"] == CatalogRevisionStatus.DRAFT
        assert "name" in response.data["diff_summary"]["added"]

    @pytest.mark.django_db
    def test_approve_catalog_revision(self, api_key_client, workspace, agent_infra_project, create_user):
        revision = CatalogRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type=CatalogEntityType.AGENT,
            entity_ref="agent/approve-test",
            revision_number=1,
            content_hash=hashlib.sha256(b"content").hexdigest(),
            content_snapshot={"name": "Agent"},
            status=CatalogRevisionStatus.DRAFT,
            created_by=create_user,
        )
        CatalogVersioningService.submit_for_approval(revision.id)

        response = api_key_client.post(
            catalog_revision_url(
                workspace.slug, agent_infra_project.id, revision.id, action="approve"
            ),
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == CatalogRevisionStatus.APPROVED
        assert response.data["approved_by"] is not None

    @pytest.mark.django_db
    def test_reject_catalog_revision(self, api_key_client, workspace, agent_infra_project, create_user):
        revision = CatalogRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type=CatalogEntityType.SKILL,
            entity_ref="skill/reject-test",
            revision_number=1,
            content_hash=hashlib.sha256(b"skill").hexdigest(),
            content_snapshot={"name": "Lint Skill"},
            status=CatalogRevisionStatus.DRAFT,
            created_by=create_user,
        )
        CatalogVersioningService.submit_for_approval(revision.id)

        response = api_key_client.post(
            catalog_revision_url(
                workspace.slug, agent_infra_project.id, revision.id, action="reject"
            ),
            {"reason": "Incomplete documentation"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == CatalogRevisionStatus.REJECTED

    @pytest.mark.django_db
    def test_rollback_catalog_revision(
        self, api_key_client, workspace, agent_infra_project, create_user
    ):
        prev = CatalogRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type=CatalogEntityType.MODEL,
            entity_ref="model/rollback-test",
            revision_number=1,
            content_hash=hashlib.sha256(b"v1").hexdigest(),
            content_snapshot={"temperature": 0.7},
            status=CatalogRevisionStatus.APPROVED,
            created_by=create_user,
        )
        current = CatalogRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type=CatalogEntityType.MODEL,
            entity_ref="model/rollback-test",
            revision_number=2,
            content_hash=hashlib.sha256(b"v2").hexdigest(),
            content_snapshot={"temperature": 1.0},
            previous_revision=prev,
            status=CatalogRevisionStatus.APPROVED,
            created_by=create_user,
        )

        response = api_key_client.post(
            catalog_revision_url(
                workspace.slug, agent_infra_project.id, current.id, action="rollback"
            ),
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["revision_number"] == 3
        assert response.data["status"] == CatalogRevisionStatus.DRAFT
        assert response.data["content_snapshot"]["temperature"] == 0.7

    @pytest.mark.django_db
    def test_compatibility_check_query(self, api_key_client, workspace, agent_infra_project):
        CompatibilityRecord.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            source_type=CompatibilityEntityType.AGENT,
            source_ref="agent/a",
            target_type=CompatibilityEntityType.MODEL,
            target_ref="model/m1",
            compatible=True,
            reason="Verified in staging",
        )
        CompatibilityRecord.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            source_type=CompatibilityEntityType.AGENT,
            source_ref="agent/b",
            target_type=CompatibilityEntityType.MODEL,
            target_ref="model/m1",
            compatible=False,
        )

        response = api_key_client.get(
            compatibility_check_url(workspace.slug, agent_infra_project.id),
            {"source_ref": "agent/a"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["compatible"] is True

    @pytest.mark.django_db
    def test_filter_catalog_revisions_by_entity(
        self, api_key_client, workspace, agent_infra_project, create_user
    ):
        CatalogRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type=CatalogEntityType.AGENT,
            entity_ref="agent/filter-a",
            revision_number=1,
            content_hash=hashlib.sha256(b"a").hexdigest(),
            content_snapshot={"a": 1},
            created_by=create_user,
        )
        CatalogRevision.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type=CatalogEntityType.SKILL,
            entity_ref="skill/filter-b",
            revision_number=1,
            content_hash=hashlib.sha256(b"b").hexdigest(),
            content_snapshot={"b": 1},
            created_by=create_user,
        )

        response = api_key_client.get(
            catalog_revision_url(workspace.slug, agent_infra_project.id),
            {"entity_type": CatalogEntityType.AGENT},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["entity_type"] == CatalogEntityType.AGENT
