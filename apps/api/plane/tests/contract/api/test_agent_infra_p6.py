# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
P6 — AgentRun observability MVP tests.

Covers:
- Progression outcome reporting (Layer 3)
- Enriched run detail (four authority layers)
- Run ledger (project-wide filtered list)
- Attention queue upgrade (review-based + progression-based items)
- Disposition auto-resolves attention items
- Artifact download with expiry enforcement
"""

import os
import tempfile

import pytest
from django.utils import timezone
from rest_framework import status

from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraAttentionItem,
    AgentRun,
    ArtifactReference,
    AuthorizingReview,
    ContextManifest,
    KnowledgeSource,
    KnowledgeVersion,
    ReviewDisposition,
)
from plane.db.models import Issue, Project, ProjectMember, State
from plane.tests.helpers.agent_infra_auth import signed_json_post


@pytest.fixture
def agent_infra_project(db, workspace, create_user):
    project = Project.objects.create(
        name="P6 Test Project",
        identifier="P6T",
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
        name="P6 Test Item",
        workspace=workspace,
        project=agent_infra_project,
        state=state,
        created_by=create_user,
    )


@pytest.fixture
def assignment(db, workspace, agent_infra_project, issue, create_user):
    return AgentAssignment.objects.create(
        workspace=workspace,
        project=agent_infra_project,
        work_item=issue,
        agent_ref="agent/dev-001",
        assignment_type="development",
        created_by=create_user,
    )


@pytest.fixture
def agent_run(db, workspace, agent_infra_project, assignment, create_user):
    return AgentRun.objects.create(
        workspace=workspace,
        project=agent_infra_project,
        assignment=assignment,
        agent_ref="agent/dev-001",
        model_used="gpt-4o",
        outcome="success",
        started_at=timezone.now(),
        correlation_id="corr-p6-001",
        created_by=create_user,
    )


@pytest.fixture
def authorizing_review(db, agent_run, create_user):
    return AuthorizingReview.objects.create(
        run=agent_run,
        reviewer_agent_ref="agent/reviewer-001",
        reviewer_model="claude-sonnet",
        verdict="accepted",
        reason="All checks passed",
        reviewed_at=timezone.now(),
        created_by=create_user,
    )


@pytest.fixture
def flagged_review(db, agent_run, create_user):
    return AuthorizingReview.objects.create(
        run=agent_run,
        reviewer_agent_ref="agent/reviewer-001",
        reviewer_model="claude-sonnet",
        verdict="flagged",
        reason="Security concern detected",
        reviewed_at=timezone.now(),
        created_by=create_user,
    )


def progression_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/progression/"
    )


def run_detail_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/"
    )


def run_ledger_url(workspace_slug, project_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/ledger/"
    )


def attention_url(workspace_slug, project_id, item_id=None):
    base = (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-attention-items/"
    )
    return f"{base}{item_id}/" if item_id else base


def artifact_download_url(workspace_slug, project_id, run_id, artifact_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/artifact-references/{artifact_id}/download/"
    )


def disposition_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/review-dispositions/"
    )


def review_url(workspace_slug, project_id, run_id):
    return (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        f"agent-runs/{run_id}/authorizing-reviews/"
    )


# --- Layer 3: Progression Reporting ---


@pytest.mark.contract
class TestProgressionReporting:
    @pytest.mark.django_db
    def test_report_auto_progress(
        self, api_key_client, workspace, agent_infra_project, agent_run, service_identity
    ):
        url = progression_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {
            "progression_outcome": "auto_progress",
            "progression_reason": "Low risk, accepted verdict",
        }
        response = signed_json_post(api_key_client, url, payload, service_identity)

        assert response.status_code == status.HTTP_200_OK
        agent_run.refresh_from_db()
        assert agent_run.progression_outcome == "auto_progress"
        assert agent_run.progression_reason == "Low risk, accepted verdict"
        assert agent_run.progression_evaluated_at is not None

    @pytest.mark.django_db
    def test_report_awaiting_disposition_creates_attention_item(
        self, api_key_client, workspace, agent_infra_project, agent_run, service_identity
    ):
        url = progression_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {"progression_outcome": "awaiting_disposition"}
        response = signed_json_post(api_key_client, url, payload, service_identity)

        assert response.status_code == status.HTTP_200_OK
        assert AgentInfraAttentionItem.objects.filter(
            entity_type="agent_run",
            entity_id=agent_run.id,
            drift_type="awaiting_disposition",
        ).exists()

    @pytest.mark.django_db
    def test_report_blocked_creates_attention_item(
        self, api_key_client, workspace, agent_infra_project, agent_run, service_identity
    ):
        url = progression_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {
            "progression_outcome": "blocked",
            "progression_reason": "Budget exceeded",
        }
        response = signed_json_post(api_key_client, url, payload, service_identity)

        assert response.status_code == status.HTTP_200_OK
        item = AgentInfraAttentionItem.objects.get(
            entity_type="agent_run",
            entity_id=agent_run.id,
            drift_type="progression_blocked",
        )
        assert item.details["progression_reason"] == "Budget exceeded"

    @pytest.mark.django_db
    def test_progression_cannot_be_set_twice(
        self, api_key_client, workspace, agent_infra_project, agent_run, service_identity
    ):
        url = progression_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {"progression_outcome": "auto_progress"}
        signed_json_post(api_key_client, url, payload, service_identity)

        payload2 = {"progression_outcome": "blocked"}
        response = signed_json_post(api_key_client, url, payload2, service_identity)

        assert response.status_code == status.HTTP_409_CONFLICT
        agent_run.refresh_from_db()
        assert agent_run.progression_outcome == "auto_progress"

    @pytest.mark.django_db
    def test_progression_invalid_value_rejected(
        self, api_key_client, workspace, agent_infra_project, agent_run, service_identity
    ):
        url = progression_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {"progression_outcome": "invalid_value"}
        response = signed_json_post(api_key_client, url, payload, service_identity)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_progression_requires_service_identity(
        self, api_key_client, workspace, agent_infra_project, agent_run
    ):
        url = progression_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {"progression_outcome": "auto_progress"}
        response = api_key_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# --- Enriched Run Detail ---


@pytest.mark.contract
class TestRunDetail:
    @pytest.mark.django_db
    def test_run_detail_returns_four_layers(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
    ):
        review = AuthorizingReview.objects.create(
            run=agent_run,
            reviewer_agent_ref="agent/reviewer",
            reviewer_model="claude-sonnet",
            verdict="accepted",
            reason="OK",
            reviewed_at=timezone.now(),
            created_by=create_user,
        )

        agent_run.progression_outcome = "awaiting_disposition"
        agent_run.progression_reason = "Medium risk"
        agent_run.progression_evaluated_at = timezone.now()
        agent_run.save()

        disposition = ReviewDisposition.objects.create(
            run=agent_run,
            reviewer=create_user,
            disposition="approved",
            reason="Looks good",
            reviewed_at=timezone.now(),
            created_by=create_user,
        )

        ArtifactReference.objects.create(
            run=agent_run,
            artifact_type="report",
            storage_ref="runs/p6/report.pdf",
            hash="sha256:abc",
            classification="internal",
            created_by=create_user,
        )

        url = run_detail_url(workspace.slug, agent_infra_project.id, agent_run.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert data["outcome"] == "success"
        assert data["progression_outcome"] == "awaiting_disposition"

        assert data["authorizing_review"] is not None
        assert data["authorizing_review"]["verdict"] == "accepted"

        assert data["review_disposition"] is not None
        assert data["review_disposition"]["disposition"] == "approved"

        assert len(data["artifact_references"]) == 1
        assert data["artifact_references"][0]["artifact_type"] == "report"

        assert data["assignment_summary"]["agent_ref"] == "agent/dev-001"
        assert data["assignment_summary"]["assignment_type"] == "development"

    @pytest.mark.django_db
    def test_run_detail_without_review_or_disposition(
        self, api_key_client, workspace, agent_infra_project, agent_run
    ):
        url = run_detail_url(workspace.slug, agent_infra_project.id, agent_run.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["authorizing_review"] is None
        assert response.data["review_disposition"] is None
        assert response.data["artifact_references"] == []
        assert response.data["progression_outcome"] is None


# --- Run Ledger ---


@pytest.mark.contract
class TestRunLedger:
    @pytest.mark.django_db
    def test_ledger_lists_all_runs(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        assignment,
        create_user,
    ):
        for i in range(3):
            AgentRun.objects.create(
                workspace=workspace,
                project=agent_infra_project,
                assignment=assignment,
                agent_ref="agent/dev-001",
                model_used="gpt-4o",
                outcome="success" if i < 2 else "failure",
                started_at=timezone.now(),
                correlation_id=f"corr-ledger-{i}",
                created_by=create_user,
            )

        url = run_ledger_url(workspace.slug, agent_infra_project.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    @pytest.mark.django_db
    def test_ledger_filters_by_outcome(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        assignment,
        create_user,
    ):
        AgentRun.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            assignment=assignment,
            agent_ref="agent/dev-001",
            model_used="gpt-4o",
            outcome="success",
            started_at=timezone.now(),
            correlation_id="corr-s",
            created_by=create_user,
        )
        AgentRun.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            assignment=assignment,
            agent_ref="agent/dev-001",
            model_used="gpt-4o",
            outcome="failure",
            started_at=timezone.now(),
            correlation_id="corr-f",
            created_by=create_user,
        )

        url = run_ledger_url(workspace.slug, agent_infra_project.id) + "?outcome=failure"
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["outcome"] == "failure"

    @pytest.mark.django_db
    def test_ledger_filters_by_progression(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        assignment,
        create_user,
    ):
        run = AgentRun.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            assignment=assignment,
            agent_ref="agent/dev-001",
            model_used="gpt-4o",
            outcome="success",
            started_at=timezone.now(),
            correlation_id="corr-prog",
            progression_outcome="awaiting_disposition",
            created_by=create_user,
        )

        url = (
            run_ledger_url(workspace.slug, agent_infra_project.id)
            + "?progression_outcome=awaiting_disposition"
        )
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    @pytest.mark.django_db
    def test_ledger_includes_verdict_and_disposition(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
    ):
        AuthorizingReview.objects.create(
            run=agent_run,
            reviewer_agent_ref="agent/reviewer",
            reviewer_model="claude-sonnet",
            verdict="flagged",
            reason="Issue found",
            reviewed_at=timezone.now(),
            created_by=create_user,
        )

        url = run_ledger_url(workspace.slug, agent_infra_project.id)
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert result["verdict"] == "flagged"


# --- Attention Queue Upgrade ---


@pytest.mark.contract
class TestAttentionQueueUpgrade:
    @pytest.mark.django_db
    def test_flagged_review_creates_attention_item(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        service_identity,
    ):
        url = review_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {
            "reviewer_agent_ref": "agent/reviewer",
            "reviewer_model": "claude-sonnet",
            "verdict": "flagged",
            "reason": "Security concern",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = signed_json_post(api_key_client, url, payload, service_identity)

        assert response.status_code == status.HTTP_201_CREATED
        assert AgentInfraAttentionItem.objects.filter(
            drift_type="review_flagged",
            entity_type="authorizing_review",
        ).exists()

    @pytest.mark.django_db
    def test_escalated_review_creates_attention_item(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        service_identity,
    ):
        url = review_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {
            "reviewer_agent_ref": "agent/reviewer",
            "reviewer_model": "claude-sonnet",
            "verdict": "escalated",
            "reason": "Critical issue",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = signed_json_post(api_key_client, url, payload, service_identity)

        assert response.status_code == status.HTTP_201_CREATED
        item = AgentInfraAttentionItem.objects.get(drift_type="review_escalated")
        assert item.details["verdict"] == "escalated"

    @pytest.mark.django_db
    def test_accepted_review_does_not_create_attention_item(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        service_identity,
    ):
        url = review_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {
            "reviewer_agent_ref": "agent/reviewer",
            "reviewer_model": "claude-sonnet",
            "verdict": "accepted",
            "reason": "All good",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = signed_json_post(api_key_client, url, payload, service_identity)

        assert response.status_code == status.HTTP_201_CREATED
        assert not AgentInfraAttentionItem.objects.filter(
            entity_type="authorizing_review",
        ).exists()

    @pytest.mark.django_db
    def test_attention_filter_by_category_review(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
    ):
        AgentInfraAttentionItem.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type="authorizing_review",
            entity_id=agent_run.id,
            drift_type="review_flagged",
            details={"verdict": "flagged"},
            created_by=create_user,
        )
        AgentInfraAttentionItem.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type="agent_assignment",
            entity_id=agent_run.id,
            drift_type="stale_assignment",
            details={},
            created_by=create_user,
        )

        url = attention_url(workspace.slug, agent_infra_project.id) + "?category=review"
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["drift_type"] == "review_flagged"

    @pytest.mark.django_db
    def test_attention_filter_by_category_drift(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
    ):
        AgentInfraAttentionItem.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type="authorizing_review",
            entity_id=agent_run.id,
            drift_type="review_flagged",
            details={},
            created_by=create_user,
        )
        AgentInfraAttentionItem.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type="agent_assignment",
            entity_id=agent_run.id,
            drift_type="stale_assignment",
            details={},
            created_by=create_user,
        )

        url = attention_url(workspace.slug, agent_infra_project.id) + "?category=drift"
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["drift_type"] == "stale_assignment"


# --- Disposition auto-resolves attention ---


@pytest.mark.contract
class TestDispositionResolvesAttention:
    @pytest.mark.django_db
    def test_disposition_resolves_review_attention_items(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
    ):
        review = AuthorizingReview.objects.create(
            run=agent_run,
            reviewer_agent_ref="agent/reviewer",
            reviewer_model="claude-sonnet",
            verdict="flagged",
            reason="Issue found",
            reviewed_at=timezone.now(),
            created_by=create_user,
        )

        review_attention = AgentInfraAttentionItem.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type="authorizing_review",
            entity_id=review.id,
            drift_type="review_flagged",
            details={"verdict": "flagged"},
            created_by=create_user,
        )
        run_attention = AgentInfraAttentionItem.objects.create(
            workspace=workspace,
            project=agent_infra_project,
            entity_type="agent_run",
            entity_id=agent_run.id,
            drift_type="awaiting_disposition",
            details={},
            created_by=create_user,
        )

        url = disposition_url(workspace.slug, agent_infra_project.id, agent_run.id)
        payload = {
            "disposition": "approved",
            "reason": "Reviewed and accepted",
            "reviewed_at": timezone.now().isoformat(),
        }
        response = api_key_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        review_attention.refresh_from_db()
        run_attention.refresh_from_db()
        assert review_attention.resolved_at is not None
        assert run_attention.resolved_at is not None


# --- Artifact Download ---


@pytest.mark.contract
class TestArtifactDownload:
    @pytest.mark.django_db
    def test_download_artifact_success(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
        settings,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.AGENT_ARTIFACTS_ROOT = tmpdir
            test_content = b"test artifact content"
            os.makedirs(os.path.join(tmpdir, "runs", "p6"), exist_ok=True)
            artifact_path = os.path.join(tmpdir, "runs", "p6", "report.txt")
            with open(artifact_path, "wb") as f:
                f.write(test_content)

            artifact = ArtifactReference.objects.create(
                run=agent_run,
                artifact_type="report",
                storage_ref="runs/p6/report.txt",
                hash="sha256:abc",
                classification="internal",
                created_by=create_user,
            )

            url = artifact_download_url(
                workspace.slug, agent_infra_project.id, agent_run.id, artifact.id
            )
            response = api_key_client.get(url)

            assert response.status_code == status.HTTP_200_OK
            assert b"".join(response.streaming_content) == test_content

    @pytest.mark.django_db
    def test_download_expired_artifact_returns_410(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
    ):
        from datetime import timedelta

        artifact = ArtifactReference.objects.create(
            run=agent_run,
            artifact_type="report",
            storage_ref="runs/p6/expired.txt",
            hash="sha256:abc",
            classification="internal",
            expires_at=timezone.now() - timedelta(hours=1),
            created_by=create_user,
        )

        url = artifact_download_url(
            workspace.slug, agent_infra_project.id, agent_run.id, artifact.id
        )
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_410_GONE

    @pytest.mark.django_db
    def test_download_nonexistent_artifact_returns_404(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
    ):
        import uuid

        url = artifact_download_url(
            workspace.slug, agent_infra_project.id, agent_run.id, uuid.uuid4()
        )
        response = api_key_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_download_path_traversal_rejected(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        agent_run,
        create_user,
        settings,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.AGENT_ARTIFACTS_ROOT = tmpdir

            artifact = ArtifactReference.objects.create(
                run=agent_run,
                artifact_type="report",
                storage_ref="../../etc/passwd",
                hash="sha256:abc",
                classification="internal",
                created_by=create_user,
            )

            url = artifact_download_url(
                workspace.slug, agent_infra_project.id, agent_run.id, artifact.id
            )
            response = api_key_client.get(url)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
