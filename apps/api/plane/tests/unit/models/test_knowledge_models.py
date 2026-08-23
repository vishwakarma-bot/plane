# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from plane.agent_infra.models import (
    AuthorityType,
    KnowledgeSource,
    KnowledgeVersion,
    SourceType,
    VALID_VERSION_TRANSITIONS,
    VersionStatus,
    validate_version_status_transition,
)
from plane.db.models import ProjectMember, State
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory


@pytest.fixture
def knowledge_setup(db):
    user = UserFactory()
    workspace = WorkspaceFactory(owner=user)
    project = ProjectFactory(workspace=workspace, created_by=user, is_agent_infra_enabled=True)
    ProjectMember.objects.create(
        project=project,
        member=user,
        role=20,
        is_active=True,
    )
    source = KnowledgeSource.objects.create(
        workspace=workspace,
        project=project,
        name="Model Test Source",
        source_type=SourceType.REPOSITORY,
        authority_type=AuthorityType.QA,
        created_by=user,
    )
    return {"user": user, "workspace": workspace, "project": project, "source": source}


@pytest.mark.unit
class TestKnowledgeModels:
    @pytest.mark.django_db
    def test_version_status_choices(self):
        assert {choice.value for choice in VersionStatus} == {
            "draft",
            "review",
            "approved",
            "rejected",
            "superseded",
            "quarantined",
        }

    @pytest.mark.django_db
    def test_valid_version_transitions(self):
        for current, allowed in VALID_VERSION_TRANSITIONS.items():
            for new_status in allowed:
                validate_version_status_transition(current, new_status)

    @pytest.mark.django_db
    def test_invalid_version_transitions(self):
        with pytest.raises(ValidationError):
            validate_version_status_transition(VersionStatus.DRAFT, VersionStatus.APPROVED)

        with pytest.raises(ValidationError):
            validate_version_status_transition(VersionStatus.SUPERSEDED, VersionStatus.DRAFT)

    @pytest.mark.django_db
    def test_agent_generated_flag(self, knowledge_setup):
        source = knowledge_setup["source"]
        user = knowledge_setup["user"]

        version = KnowledgeVersion(
            source=source,
            workspace=knowledge_setup["workspace"],
            project=knowledge_setup["project"],
            version_number=1,
            content_hash=hashlib.sha256(b"agent").hexdigest(),
            is_agent_generated=True,
            status=VersionStatus.QUARANTINED,
            created_by=user,
        )
        version.save()
        assert version.status == VersionStatus.QUARANTINED

        invalid_version = KnowledgeVersion(
            source=source,
            workspace=knowledge_setup["workspace"],
            project=knowledge_setup["project"],
            version_number=2,
            content_hash=hashlib.sha256(b"bad").hexdigest(),
            is_agent_generated=True,
            status=VersionStatus.DRAFT,
            created_by=user,
        )
        with pytest.raises(ValidationError):
            invalid_version.full_clean()

        with pytest.raises(ValidationError):
            validate_version_status_transition(
                VersionStatus.QUARANTINED,
                VersionStatus.APPROVED,
                is_agent_generated=True,
            )

    @pytest.mark.django_db
    def test_unique_version_number_per_source(self, knowledge_setup):
        source = knowledge_setup["source"]
        user = knowledge_setup["user"]

        KnowledgeVersion.objects.create(
            source=source,
            workspace=knowledge_setup["workspace"],
            project=knowledge_setup["project"],
            version_number=1,
            content_hash=hashlib.sha256(b"v1").hexdigest(),
            created_by=user,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                KnowledgeVersion.objects.create(
                    source=source,
                    workspace=knowledge_setup["workspace"],
                    project=knowledge_setup["project"],
                    version_number=1,
                    content_hash=hashlib.sha256(b"v1-dup").hexdigest(),
                    created_by=user,
                )

    @pytest.mark.django_db
    def test_knowledge_source_retirement(self, knowledge_setup):
        source = knowledge_setup["source"]
        source.is_retired = True
        source.retired_at = timezone.now()
        source.save(update_fields=["is_retired", "retired_at", "updated_at"])

        source.refresh_from_db()
        assert source.is_retired is True
        assert source.retired_at is not None
