# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from plane.agent_infra.decorators import idempotent_callback
from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraAttentionItem,
    AgentInfraOutbox,
    AgentRun,
    AssignmentStatus,
    AssignmentType,
    AuthorizingReview,
    IdempotencyRecord,
    OutboxEventType,
    OutboxStatus,
    ReviewVerdict,
    RunOutcome,
)
from plane.agent_infra.services.reconciliation import ReconciliationService
from plane.db.models import Issue, ProjectMember, State
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory


@pytest.fixture
def reconciliation_setup(db):
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
        name="Reconciliation Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
    )
    assignment = AgentAssignment.objects.create(
        workspace=workspace,
        project=project,
        work_item=issue,
        agent_ref="agent/reconciliation-test",
        assignment_type=AssignmentType.DEVELOPMENT,
        created_by=user,
    )
    return {
        "user": user,
        "workspace": workspace,
        "project": project,
        "issue": issue,
        "assignment": assignment,
    }


@pytest.mark.unit
class TestAgentInfraReconciliation:
    @pytest.mark.django_db
    def test_outbox_event_creation(self, reconciliation_setup):
        project = reconciliation_setup["project"]
        workspace = reconciliation_setup["workspace"]

        event = AgentInfraOutbox.objects.create(
            workspace=workspace,
            project=project,
            event_type=OutboxEventType.ASSIGNMENT_CREATED,
            payload={"assignment_id": str(uuid4())},
        )

        assert event.status == OutboxStatus.PENDING
        assert event.attempts == 0
        assert event.max_attempts == 5
        assert event.idempotency_key is not None

    @pytest.mark.django_db
    @patch("plane.agent_infra.services.reconciliation.pinned_fetch")
    def test_outbox_retry_with_backoff(self, mock_pinned_fetch, reconciliation_setup, settings):
        settings.DEVELOPMENT_CENTER_EVENT_URL = "https://development-center.example/events"
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service unavailable"
        mock_pinned_fetch.return_value = mock_response

        event = AgentInfraOutbox.objects.create(
            workspace=reconciliation_setup["workspace"],
            project=reconciliation_setup["project"],
            event_type=OutboxEventType.ASSIGNMENT_CREATED,
            payload={"assignment_id": str(reconciliation_setup["assignment"].id)},
        )
        AgentInfraOutbox.objects.exclude(pk=event.pk).delete()

        service = ReconciliationService()
        with freeze_time("2026-08-23T12:00:00Z"):
            result = service.process_outbox()
            expected_next = timezone.now() + timedelta(seconds=60)

        event.refresh_from_db()
        assert result["retried"] == 1
        assert event.status == OutboxStatus.PENDING
        assert event.attempts == 1
        assert event.next_attempt_at == expected_next

    @pytest.mark.django_db
    @patch("plane.agent_infra.services.reconciliation.pinned_fetch")
    def test_outbox_max_attempts_reached(self, mock_pinned_fetch, reconciliation_setup, settings):
        settings.DEVELOPMENT_CENTER_EVENT_URL = "https://development-center.example/events"
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"
        mock_pinned_fetch.return_value = mock_response

        event = AgentInfraOutbox.objects.create(
            workspace=reconciliation_setup["workspace"],
            project=reconciliation_setup["project"],
            event_type=OutboxEventType.DISPOSITION_CREATED,
            payload={"disposition_id": str(uuid4())},
            attempts=4,
            max_attempts=5,
        )

        service = ReconciliationService()
        result = service.process_outbox()

        event.refresh_from_db()
        assert result["failed"] == 1
        assert event.status == OutboxStatus.FAILED
        assert event.attempts == 5
        assert "Development Center callback failed" in event.error_message

    @pytest.mark.django_db
    def test_idempotency_duplicate_request(self):
        factory = APIRequestFactory()
        idempotency_key = uuid4()

        class DummyView:
            call_count = 0

            @idempotent_callback
            def post(self, request):
                DummyView.call_count += 1
                return Response({"ok": True}, status=201)

        view = DummyView()
        request = factory.post(
            "/callbacks/test/",
            {"value": "same"},
            format="json",
            HTTP_X_IDEMPOTENCY_KEY=str(idempotency_key),
        )

        first_response = view.post(request)
        second_response = view.post(request)

        assert first_response.status_code == 201
        assert second_response.status_code == 201
        assert second_response.data == first_response.data
        assert DummyView.call_count == 1
        assert IdempotencyRecord.objects.filter(idempotency_key=idempotency_key).count() == 1

    @pytest.mark.django_db
    def test_idempotency_expiry(self):
        idempotency_key = uuid4()
        IdempotencyRecord.objects.create(
            idempotency_key=idempotency_key,
            fingerprint_hash="expired-test-fingerprint",
            response_status=200,
            response_body={"cached": True},
            expires_at=timezone.now() - timedelta(hours=1),
        )

        service = ReconciliationService()
        deleted_count = service.cleanup_expired_idempotency()

        assert deleted_count == 1
        assert not IdempotencyRecord.objects.filter(idempotency_key=idempotency_key).exists()

    @pytest.mark.django_db
    def test_stale_assignment_detection(self, reconciliation_setup):
        assignment = reconciliation_setup["assignment"]
        AgentAssignment.objects.filter(pk=assignment.pk).update(
            status=AssignmentStatus.RUNNING,
            updated_at=timezone.now() - timedelta(minutes=45),
        )

        service = ReconciliationService()
        stale_assignments, attention_items = service.check_stale_assignments(
            reconciliation_setup["workspace"].id,
            reconciliation_setup["project"].id,
        )

        assert len(stale_assignments) == 1
        assert stale_assignments[0].id == assignment.id
        assert len(attention_items) == 1
        assert attention_items[0].drift_type == "stale_assignment"
        assert AgentInfraAttentionItem.objects.filter(
            entity_id=assignment.id,
            drift_type="stale_assignment",
        ).exists()

    @pytest.mark.django_db
    def test_orphaned_run_detection(self, reconciliation_setup):
        assignment = reconciliation_setup["assignment"]
        run = AgentRun.objects.create(
            workspace=reconciliation_setup["workspace"],
            project=reconciliation_setup["project"],
            assignment=assignment,
            agent_ref="agent/reconciliation-test",
            model_used="gpt-4o",
            outcome=RunOutcome.SUCCESS,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(minutes=45),
            correlation_id="corr-orphaned-run",
            created_by=reconciliation_setup["user"],
        )

        service = ReconciliationService()
        orphaned_runs, attention_items = service.check_orphaned_runs(
            reconciliation_setup["workspace"].id,
            reconciliation_setup["project"].id,
        )

        assert len(orphaned_runs) == 1
        assert orphaned_runs[0].id == run.id
        assert len(attention_items) == 1
        assert attention_items[0].drift_type == "orphaned_run"

    @pytest.mark.django_db
    def test_status_reconciliation(self, reconciliation_setup):
        assignment = reconciliation_setup["assignment"]
        AgentAssignment.objects.filter(pk=assignment.pk).update(status=AssignmentStatus.RUNNING)
        AgentRun.objects.create(
            workspace=reconciliation_setup["workspace"],
            project=reconciliation_setup["project"],
            assignment=assignment,
            agent_ref="agent/reconciliation-test",
            model_used="gpt-4o",
            outcome=RunOutcome.SUCCESS,
            started_at=timezone.now() - timedelta(minutes=10),
            completed_at=timezone.now() - timedelta(minutes=5),
            correlation_id="corr-status-drift",
            created_by=reconciliation_setup["user"],
        )

        service = ReconciliationService()
        result = service.reconcile_assignment_status(assignment.id)

        assert result["drift_detected"] is True
        assert result["current_status"] == AssignmentStatus.RUNNING
        assert result["expected_status"] == AssignmentStatus.COMPLETED
        assert AgentInfraAttentionItem.objects.filter(
            entity_id=assignment.id,
            drift_type="status_mismatch",
        ).exists()

    @pytest.mark.django_db
    def test_status_reconciliation_no_drift_when_aligned(self, reconciliation_setup):
        assignment = reconciliation_setup["assignment"]
        AgentAssignment.objects.filter(pk=assignment.pk).update(status=AssignmentStatus.COMPLETED)
        run = AgentRun.objects.create(
            workspace=reconciliation_setup["workspace"],
            project=reconciliation_setup["project"],
            assignment=assignment,
            agent_ref="agent/reconciliation-test",
            model_used="gpt-4o",
            outcome=RunOutcome.SUCCESS,
            started_at=timezone.now() - timedelta(minutes=10),
            completed_at=timezone.now() - timedelta(minutes=5),
            correlation_id="corr-status-aligned",
            created_by=reconciliation_setup["user"],
        )
        AuthorizingReview.objects.create(
            run=run,
            reviewer_agent_ref="agent/reviewer",
            reviewer_model="claude-3-opus",
            verdict=ReviewVerdict.ACCEPTED,
            reason="Looks good.",
            reviewed_at=timezone.now(),
            created_by=reconciliation_setup["user"],
        )

        service = ReconciliationService()
        result = service.reconcile_assignment_status(assignment.id)

        assert result["drift_detected"] is False
