# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from plane.agent_infra.models import (
    AgentAssignment,
    AgentRun,
    ArtifactClassification,
    ArtifactReference,
    ArtifactType,
    AssignmentStatus,
    AssignmentType,
    AuthorizingReview,
    DispositionChoice,
    ReviewDisposition,
    ReviewVerdict,
    RunOutcome,
)
from plane.db.models import Issue, ProjectMember, State
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory


@pytest.fixture
def agent_infra_setup(db):
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
        name="Model Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
    )
    assignment = AgentAssignment.objects.create(
        workspace=workspace,
        project=project,
        work_item=issue,
        agent_ref="agent/model-test",
        assignment_type=AssignmentType.DEVELOPMENT,
        created_by=user,
    )
    run = AgentRun.objects.create(
        workspace=workspace,
        project=project,
        assignment=assignment,
        agent_ref="agent/model-test",
        model_used="gpt-4o",
        outcome=RunOutcome.SUCCESS,
        started_at=timezone.now(),
        correlation_id="corr-model-test",
        created_by=user,
    )
    return {
        "user": user,
        "workspace": workspace,
        "project": project,
        "issue": issue,
        "assignment": assignment,
        "run": run,
    }


@pytest.mark.unit
class TestAgentInfraModels:
    @pytest.mark.django_db
    def test_agent_assignment_choices(self):
        assert {choice.value for choice in AssignmentType} == {
            "qa",
            "development",
            "review",
            "research",
        }
        assert {choice.value for choice in AssignmentStatus} == {
            "pending",
            "running",
            "completed",
            "failed",
            "cancelled",
        }

    @pytest.mark.django_db
    def test_agent_run_default_values(self, agent_infra_setup):
        run = agent_infra_setup["run"]
        assert run.tokens_in == 0
        assert run.tokens_out == 0

    @pytest.mark.django_db
    def test_authorizing_review_model_validation(self, agent_infra_setup):
        run = agent_infra_setup["run"]
        review = AuthorizingReview(
            run=run,
            reviewer_agent_ref="agent/reviewer",
            reviewer_model=run.model_used,
            verdict=ReviewVerdict.ACCEPTED,
            reason="Same model should fail validation.",
            reviewed_at=timezone.now(),
        )

        with pytest.raises(ValidationError) as exc_info:
            review.full_clean()

        assert "reviewer_model" in exc_info.value.message_dict

    @pytest.mark.django_db
    def test_artifact_reference_classification_choices(self):
        assert {choice.value for choice in ArtifactType} == {
            "screenshot",
            "log",
            "diff",
            "report",
            "trace",
        }
        assert {choice.value for choice in ArtifactClassification} == {
            "public",
            "internal",
            "sensitive",
        }

    @pytest.mark.django_db
    def test_review_disposition_choices(self):
        assert {choice.value for choice in DispositionChoice} == {
            "approved",
            "rejected",
            "rework",
        }

    @pytest.mark.django_db
    def test_soft_delete(self, agent_infra_setup):
        user = agent_infra_setup["user"]
        run = agent_infra_setup["run"]

        assignment = agent_infra_setup["assignment"]
        assignment.delete()
        assert AgentAssignment.objects.filter(pk=assignment.pk).count() == 0
        assert AgentAssignment.all_objects.filter(pk=assignment.pk, deleted_at__isnull=False).exists()

        review = AuthorizingReview.objects.create(
            run=run,
            reviewer_agent_ref="agent/reviewer",
            reviewer_model="claude-3-opus",
            verdict=ReviewVerdict.ACCEPTED,
            reason="Approved.",
            reviewed_at=timezone.now(),
            created_by=user,
        )
        review.delete()
        assert AuthorizingReview.objects.filter(pk=review.pk).count() == 0
        assert AuthorizingReview.all_objects.filter(pk=review.pk, deleted_at__isnull=False).exists()

        artifact = ArtifactReference.objects.create(
            run=run,
            artifact_type=ArtifactType.LOG,
            storage_ref="s3://bucket/log.txt",
            hash="hash-001",
            classification=ArtifactClassification.INTERNAL,
            created_by=user,
        )
        artifact.delete()
        assert ArtifactReference.objects.filter(pk=artifact.pk).count() == 0
        assert ArtifactReference.all_objects.filter(pk=artifact.pk, deleted_at__isnull=False).exists()

        disposition = ReviewDisposition.objects.create(
            run=run,
            reviewer=user,
            disposition=DispositionChoice.APPROVED,
            reason="Approved.",
            reviewed_at=timezone.now(),
            created_by=user,
        )
        disposition.delete()
        assert ReviewDisposition.objects.filter(pk=disposition.pk).count() == 0
        assert ReviewDisposition.all_objects.filter(pk=disposition.pk, deleted_at__isnull=False).exists()

        run.delete()
        assert AgentRun.objects.filter(pk=run.pk).count() == 0
        assert AgentRun.all_objects.filter(pk=run.pk, deleted_at__isnull=False).exists()
