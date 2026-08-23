# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraAttentionItem,
    AgentInfraOutbox,
    AgentRun,
    AssignmentStatus,
    AssignmentType,
    OutboxEventType,
    OutboxStatus,
    ReviewDisposition,
    RunOutcome,
)
from plane.agent_infra.services.reconciliation import ReconciliationService
from plane.db.models import Issue, ProjectMember, State
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory


@pytest.fixture
def signals_setup(db):
    user = UserFactory()
    workspace = WorkspaceFactory(owner=user)
    project = ProjectFactory(workspace=workspace, created_by=user, is_agent_infra_enabled=True)
    ProjectMember.objects.create(
        project=project,
        member=user,
        role=20,
        is_active=True,
    )
    state = State.objects.create(
        name="Todo",
        project=project,
        workspace=workspace,
        group="backlog",
        default=True,
    )
    issue = Issue.objects.create(
        name="Signals Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
    )
    return {
        "user": user,
        "workspace": workspace,
        "project": project,
        "issue": issue,
    }


def attention_items_url(workspace_slug, project_id, attention_item_id=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-attention-items/"
    return f"{base}{attention_item_id}/" if attention_item_id else base


def sync_status_url(workspace_slug, project_id):
    return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-sync-status/"


@pytest.fixture
def api_key_client_for_signals(api_client, signals_setup):
    from plane.db.models.api import APIToken

    token = APIToken.objects.create(
        user=signals_setup["user"],
        label="Signals Test API Token",
        token="signals-test-api-token",
    )
    api_client.credentials(HTTP_X_API_KEY=token.token)
    return api_client


@pytest.mark.unit
class TestAgentInfraSignals:
    @pytest.mark.django_db
    def test_assignment_creation_triggers_outbox_event(self, signals_setup):
        assignment = AgentAssignment.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            work_item=signals_setup["issue"],
            agent_ref="agent/signals-test",
            assignment_type=AssignmentType.DEVELOPMENT,
            created_by=signals_setup["user"],
        )

        event = AgentInfraOutbox.objects.get(
            event_type=OutboxEventType.ASSIGNMENT_CREATED,
            payload__assignment_id=str(assignment.id),
        )
        assert event.status == OutboxStatus.PENDING
        assert event.payload["work_item_id"] == str(signals_setup["issue"].id)
        assert event.payload["agent_ref"] == "agent/signals-test"

    @pytest.mark.django_db
    def test_assignment_cancellation_triggers_outbox_event(self, signals_setup):
        assignment = AgentAssignment.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            work_item=signals_setup["issue"],
            agent_ref="agent/signals-test",
            assignment_type=AssignmentType.DEVELOPMENT,
            created_by=signals_setup["user"],
        )

        assignment.status = AssignmentStatus.CANCELLED
        assignment.save()

        event = AgentInfraOutbox.objects.get(
            event_type=OutboxEventType.ASSIGNMENT_CANCELLED,
            payload__assignment_id=str(assignment.id),
        )
        assert event.payload["status"] == AssignmentStatus.CANCELLED

    @pytest.mark.django_db
    def test_disposition_creation_triggers_outbox_event(self, signals_setup):
        assignment = AgentAssignment.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            work_item=signals_setup["issue"],
            agent_ref="agent/signals-test",
            assignment_type=AssignmentType.DEVELOPMENT,
            created_by=signals_setup["user"],
        )
        run = AgentRun.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            assignment=assignment,
            agent_ref="agent/signals-test",
            model_used="gpt-4o",
            outcome=RunOutcome.SUCCESS,
            started_at=timezone.now(),
            correlation_id="corr-signals-disposition",
            created_by=signals_setup["user"],
        )
        disposition = ReviewDisposition.objects.create(
            run=run,
            reviewer=signals_setup["user"],
            disposition="approved",
            reason="Looks good.",
            reviewed_at=timezone.now(),
            created_by=signals_setup["user"],
        )

        event = AgentInfraOutbox.objects.get(
            event_type=OutboxEventType.DISPOSITION_CREATED,
            payload__disposition_id=str(disposition.id),
        )
        assert event.payload["run_id"] == str(run.id)
        assert event.payload["disposition"] == "approved"


@pytest.mark.unit
class TestAgentInfraAttentionItemsAPI:
    @pytest.mark.django_db
    def test_attention_items_api_returns_unresolved_items(
        self, api_key_client_for_signals, signals_setup
    ):
        unresolved = AgentInfraAttentionItem.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            entity_type="AgentAssignment",
            entity_id=signals_setup["issue"].id,
            drift_type="stale_assignment",
            details={"assignment_id": str(signals_setup["issue"].id)},
            created_by=signals_setup["user"],
        )
        AgentInfraAttentionItem.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            entity_type="AgentRun",
            entity_id=signals_setup["issue"].id,
            drift_type="orphaned_run",
            details={"run_id": str(signals_setup["issue"].id)},
            resolved_at=timezone.now(),
            created_by=signals_setup["user"],
        )

        response = api_key_client_for_signals.get(
            attention_items_url(signals_setup["workspace"].slug, signals_setup["project"].id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == unresolved.id

    @pytest.mark.django_db
    def test_attention_items_api_filters_by_drift_type(
        self, api_key_client_for_signals, signals_setup
    ):
        AgentInfraAttentionItem.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            entity_type="AgentAssignment",
            entity_id=signals_setup["issue"].id,
            drift_type="stale_assignment",
            details={},
            created_by=signals_setup["user"],
        )
        AgentInfraAttentionItem.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            entity_type="AgentRun",
            entity_id=signals_setup["issue"].id,
            drift_type="orphaned_run",
            details={},
            created_by=signals_setup["user"],
        )

        response = api_key_client_for_signals.get(
            attention_items_url(signals_setup["workspace"].slug, signals_setup["project"].id),
            {"drift_type": "stale_assignment"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["drift_type"] == "stale_assignment"

    @pytest.mark.django_db
    def test_attention_items_can_be_resolved_via_patch(
        self, api_key_client_for_signals, signals_setup
    ):
        attention_item = AgentInfraAttentionItem.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            entity_type="AgentAssignment",
            entity_id=signals_setup["issue"].id,
            drift_type="stale_assignment",
            details={},
            created_by=signals_setup["user"],
        )

        response = api_key_client_for_signals.patch(
            attention_items_url(
                signals_setup["workspace"].slug,
                signals_setup["project"].id,
                attention_item.id,
            ),
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["resolved_at"] is not None

        attention_item.refresh_from_db()
        assert attention_item.resolved_at is not None


@pytest.mark.unit
class TestAgentSyncStatusAPI:
    @pytest.mark.django_db
    def test_sync_status_endpoint_returns_correct_counts(
        self, api_key_client_for_signals, signals_setup
    ):
        delivery_time = timezone.now() - timedelta(minutes=10)
        AgentInfraOutbox.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            event_type=OutboxEventType.ASSIGNMENT_CREATED,
            payload={"assignment_id": "pending-1"},
            status=OutboxStatus.PENDING,
        )
        AgentInfraOutbox.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            event_type=OutboxEventType.ASSIGNMENT_CREATED,
            payload={"assignment_id": "sent-1"},
            status=OutboxStatus.SENT,
            last_attempted_at=delivery_time,
        )
        AgentInfraAttentionItem.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            entity_type="AgentAssignment",
            entity_id=signals_setup["issue"].id,
            drift_type="stale_assignment",
            details={},
            created_by=signals_setup["user"],
        )
        AgentInfraAttentionItem.objects.create(
            workspace=signals_setup["workspace"],
            project=signals_setup["project"],
            entity_type="AgentRun",
            entity_id=signals_setup["issue"].id,
            drift_type="orphaned_run",
            details={},
            created_by=signals_setup["user"],
        )

        service = ReconciliationService()
        service.reconcile(
            workspace_id=signals_setup["workspace"].id,
            project_id=signals_setup["project"].id,
        )

        response = api_key_client_for_signals.get(
            sync_status_url(signals_setup["workspace"].slug, signals_setup["project"].id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pending_outbox_count"] == 1
        assert response.data["stale_assignment_count"] == 1
        assert response.data["orphaned_run_count"] == 1
        assert response.data["last_outbox_delivery_at"] is not None
        assert response.data["last_reconciliation_at"] is not None
