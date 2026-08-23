# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from plane.agent_infra.models import (
    AgentAssignment,
    AgentRun,
    AssignmentType,
    AuthorityType,
    ContextManifest,
    KnowledgeSource,
    KnowledgeVersion,
    RunOutcome,
    SourceType,
    VersionStatus,
)
from plane.agent_infra.services.context_manifest import ContextManifestService
from plane.db.models import Issue, ProjectMember, State
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory


@pytest.fixture
def manifest_setup(db):
    user = UserFactory()
    workspace = WorkspaceFactory(owner=user)
    project = ProjectFactory(
        workspace=workspace,
        created_by=user,
        is_agent_infra_enabled=True,
        name="Manifest Primary Project",
        identifier="MPR1",
    )
    other_project = ProjectFactory(
        workspace=workspace,
        created_by=user,
        is_agent_infra_enabled=True,
        name="Manifest Other Project",
        identifier="MOT1",
    )
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
        name="Manifest Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
    )
    assignment = AgentAssignment.objects.create(
        workspace=workspace,
        project=project,
        work_item=issue,
        agent_ref="agent/manifest-test",
        assignment_type=AssignmentType.DEVELOPMENT,
        created_by=user,
    )
    run = AgentRun.objects.create(
        workspace=workspace,
        project=project,
        assignment=assignment,
        agent_ref="agent/manifest-test",
        model_used="gpt-4o",
        outcome=RunOutcome.SUCCESS,
        started_at=timezone.now(),
        correlation_id="corr-manifest-test",
        created_by=user,
    )
    source = KnowledgeSource.objects.create(
        workspace=workspace,
        project=project,
        name="Runbook",
        source_type=SourceType.PLANE,
        authority_type=AuthorityType.PLATFORM,
        created_by=user,
    )
    version = KnowledgeVersion.objects.create(
        source=source,
        workspace=workspace,
        project=project,
        version_number=1,
        status=VersionStatus.APPROVED,
        content_hash="hash-1",
        created_by=user,
    )
    other_source = KnowledgeSource.objects.create(
        workspace=workspace,
        project=other_project,
        name="Other Project Source",
        source_type=SourceType.PLANE,
        authority_type=AuthorityType.QA,
        created_by=user,
    )
    other_version = KnowledgeVersion.objects.create(
        source=other_source,
        workspace=workspace,
        project=other_project,
        version_number=1,
        status=VersionStatus.APPROVED,
        content_hash="hash-other",
        created_by=user,
    )
    return {
        "user": user,
        "workspace": workspace,
        "project": project,
        "run": run,
        "source": source,
        "version": version,
        "other_version": other_version,
    }


@pytest.mark.unit
class TestContextManifestService:
    @pytest.mark.django_db
    def test_bind_versions_to_run(self, manifest_setup):
        service = ContextManifestService()
        manifests = service.bind_versions_to_run(
            manifest_setup["run"],
            [manifest_setup["version"].id],
        )

        assert len(manifests) == 1
        assert ContextManifest.objects.filter(run=manifest_setup["run"]).count() == 1
        assert service.get_run_manifest(manifest_setup["run"].id) == [manifest_setup["version"]]

    @pytest.mark.django_db
    def test_bind_rejects_cross_project_versions(self, manifest_setup):
        service = ContextManifestService()
        run = manifest_setup["run"]
        other_version = manifest_setup["other_version"]

        assert other_version.project_id != run.project_id

        with pytest.raises(ValidationError, match="different workspace/project"):
            service.bind_versions_to_run(run, [other_version.id])

    @pytest.mark.django_db
    def test_get_downstream_impact(self, manifest_setup):
        service = ContextManifestService()
        service.bind_versions_to_run(manifest_setup["run"], [manifest_setup["version"].id])

        impacted_runs = service.get_downstream_impact(manifest_setup["version"].id)

        assert len(impacted_runs) == 1
        assert impacted_runs[0].id == manifest_setup["run"].id

    @pytest.mark.django_db
    def test_manifest_freshness_with_superseded_version(self, manifest_setup):
        version = manifest_setup["version"]
        service = ContextManifestService()
        service.bind_versions_to_run(manifest_setup["run"], [version.id])

        version.status = VersionStatus.SUPERSEDED
        version.save(update_fields=["status", "updated_at"])

        is_fresh, stale_items = service.check_manifest_freshness(manifest_setup["run"].id)

        assert is_fresh is False
        assert len(stale_items) == 1
        assert stale_items[0]["issue_type"] == "superseded"

    @pytest.mark.django_db
    def test_manifest_freshness_when_all_current(self, manifest_setup):
        source = manifest_setup["source"]
        source.expires_at = timezone.now() + timedelta(days=30)
        source.save(update_fields=["expires_at", "updated_at"])

        service = ContextManifestService()
        service.bind_versions_to_run(manifest_setup["run"], [manifest_setup["version"].id])

        is_fresh, stale_items = service.check_manifest_freshness(manifest_setup["run"].id)

        assert is_fresh is True
        assert stale_items == []
