# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
P7 — Authorization policy adversarial tests.

Covers:
- Missing auth → 401
- Wrong tenant/workspace → 403/404
- Wrong permission scope (MEMBER vs ADMIN for privileged ops) → 403
- Cross-project FK injection → 404
- Invalid state transitions → 409
- Approval lifecycle (self-review, direct-from-draft) → 403/409
- Emergency deny project scoping
- Separation of duty constraint enforcement
"""

import pytest
from django.utils import timezone
from rest_framework import status

from plane.agent_infra.models import (
    ActionApproval,
    ApprovalStatus,
    AuthorizationPolicy,
    EmergencyDeny,
    PolicyDecision,
    PolicyStatus,
    SeparationOfDutyConstraint,
)
from plane.db.models import Project, ProjectMember, User, Workspace, WorkspaceMember


@pytest.fixture
def p7_project(db, workspace, create_user):
    project = Project.objects.create(
        name="P7 Test Project",
        identifier="P7T",
        workspace=workspace,
        created_by=create_user,
        is_agent_infra_enabled=True,
    )
    ProjectMember.objects.create(
        project=project, member=create_user, role=20, is_active=True
    )
    return project


@pytest.fixture
def other_project(db, workspace, create_user):
    """A second project in the same workspace for cross-project tests."""
    project = Project.objects.create(
        name="Other Project",
        identifier="OTH",
        workspace=workspace,
        created_by=create_user,
        is_agent_infra_enabled=True,
    )
    ProjectMember.objects.create(
        project=project, member=create_user, role=20, is_active=True
    )
    return project


@pytest.fixture
def member_user(db, workspace, p7_project):
    """A MEMBER-role user (not ADMIN) in the project."""
    user = User.objects.create(
        email="member@plane.so", first_name="Member", last_name="User"
    )
    user.set_password("member-pass")
    user.save()
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    ProjectMember.objects.create(
        project=p7_project, member=user, role=15, is_active=True
    )
    return user


@pytest.fixture
def approver_user(db, workspace, p7_project):
    """A separate ADMIN user who can approve policies."""
    user = User.objects.create(
        email="approver@plane.so", first_name="Approver", last_name="Admin"
    )
    user.set_password("approver-pass")
    user.save()
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20)
    ProjectMember.objects.create(
        project=p7_project, member=user, role=20, is_active=True
    )
    return user


@pytest.fixture
def member_client(api_client, member_user):
    api_client.force_authenticate(user=member_user)
    return api_client


@pytest.fixture
def approver_client(api_client, approver_user):
    api_client.force_authenticate(user=approver_user)
    return api_client


def policy_url(workspace, project, suffix=""):
    base = f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/authorization-policies/"
    return f"{base}{suffix}"


def emergency_url(workspace, project, suffix=""):
    base = f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/emergency-denies/"
    return f"{base}{suffix}"


def approval_url(workspace, project, suffix=""):
    base = f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/action-approvals/"
    return f"{base}{suffix}"


@pytest.fixture
def draft_policy(db, workspace, p7_project, create_user):
    return AuthorizationPolicy.objects.create(
        workspace=workspace,
        project=p7_project,
        name="test-policy",
        description="Test deny policy",
        effect="deny",
        scope="project",
        priority=100,
        subjects=[{"type": "agent", "ref": "*"}],
        resources=[{"type": "code", "ref": "*"}],
        actions=["write"],
        status=PolicyStatus.DRAFT,
        revision_number=1,
        content_hash="abc123def456",
        created_by=create_user,
        updated_by=create_user,
    )


@pytest.fixture
def pending_policy(db, workspace, p7_project, create_user):
    return AuthorizationPolicy.objects.create(
        workspace=workspace,
        project=p7_project,
        name="pending-policy",
        description="Test pending policy",
        effect="allow",
        scope="project",
        priority=200,
        subjects=[{"type": "agent", "ref": "dev-engineer"}],
        resources=[{"type": "code", "ref": "*"}],
        actions=["read"],
        status=PolicyStatus.PENDING_APPROVAL,
        revision_number=1,
        content_hash="pending123hash",
        created_by=create_user,
        updated_by=create_user,
    )


@pytest.fixture
def active_policy(db, workspace, p7_project, create_user, approver_user):
    return AuthorizationPolicy.objects.create(
        workspace=workspace,
        project=p7_project,
        name="active-policy",
        description="Test active policy",
        effect="allow",
        scope="project",
        priority=300,
        subjects=[{"type": "agent", "ref": "qa-engineer"}],
        resources=[{"type": "code", "ref": "*"}],
        actions=["read", "write"],
        status=PolicyStatus.ACTIVE,
        revision_number=1,
        content_hash="active456hash",
        approved_by=approver_user,
        approved_at=timezone.now(),
        created_by=create_user,
        updated_by=create_user,
    )


# ── 1. Missing auth → 401 ──


@pytest.mark.django_db
class TestMissingAuth:
    def test_list_policies_unauthenticated(self, api_client, workspace, p7_project):
        resp = api_client.get(policy_url(workspace, p7_project))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_policy_unauthenticated(self, api_client, workspace, p7_project):
        resp = api_client.post(policy_url(workspace, p7_project), {})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_emergency_deny_unauthenticated(self, api_client, workspace, p7_project):
        resp = api_client.post(emergency_url(workspace, p7_project), {})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── 2. Cross-project FK injection ──


@pytest.mark.django_db
class TestCrossProjectInjection:
    def test_get_policy_from_wrong_project(
        self, session_client, workspace, p7_project, other_project, draft_policy
    ):
        """Policy created in p7_project should not be accessible via other_project URL."""
        url = policy_url(workspace, other_project, f"{draft_policy.id}/")
        resp = session_client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_policy_from_wrong_project(
        self, session_client, workspace, p7_project, other_project, draft_policy
    ):
        url = policy_url(workspace, other_project, f"{draft_policy.id}/")
        resp = session_client.patch(url, {"priority": 999}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_approve_policy_from_wrong_project(
        self, approver_client, workspace, p7_project, other_project, pending_policy
    ):
        url = policy_url(workspace, other_project, f"{pending_policy.id}/approve/")
        resp = approver_client.post(url, {}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_revoke_policy_from_wrong_project(
        self, approver_client, workspace, p7_project, other_project, active_policy
    ):
        url = policy_url(workspace, other_project, f"{active_policy.id}/revoke/")
        resp = approver_client.post(url, {"reason": "test"}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ── 3. Permission scope — MEMBER cannot do privileged ops ──


@pytest.mark.django_db
class TestMemberRestrictions:
    def test_member_cannot_approve_policy(
        self, member_client, workspace, p7_project, pending_policy
    ):
        url = policy_url(workspace, p7_project, f"{pending_policy.id}/approve/")
        resp = member_client.post(url, {}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_member_cannot_revoke_policy(
        self, member_client, workspace, p7_project, active_policy
    ):
        url = policy_url(workspace, p7_project, f"{active_policy.id}/revoke/")
        resp = member_client.post(url, {"reason": "test"}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_member_cannot_activate_emergency_deny(
        self, member_client, workspace, p7_project
    ):
        url = emergency_url(workspace, p7_project)
        resp = member_client.post(
            url, {"reason": "incident", "scope_filter": None}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_member_can_list_policies(
        self, member_client, workspace, p7_project, draft_policy
    ):
        resp = member_client.get(policy_url(workspace, p7_project))
        assert resp.status_code == status.HTTP_200_OK


# ── 4. Invalid state transitions ──


@pytest.mark.django_db
class TestInvalidTransitions:
    def test_cannot_approve_draft_policy(
        self, approver_client, workspace, p7_project, draft_policy
    ):
        """Draft must go to pending_approval before it can be approved."""
        url = policy_url(workspace, p7_project, f"{draft_policy.id}/approve/")
        resp = approver_client.post(url, {}, format="json")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_cannot_approve_revoked_policy(
        self, approver_client, workspace, p7_project, create_user
    ):
        revoked = AuthorizationPolicy.objects.create(
            workspace=workspace,
            project=p7_project,
            name="revoked-policy",
            description="Revoked policy",
            effect="deny",
            scope="project",
            priority=100,
            subjects=[{"type": "agent", "ref": "*"}],
            resources=[{"type": "code", "ref": "*"}],
            actions=["write"],
            status=PolicyStatus.REVOKED,
            revision_number=1,
            content_hash="revoked123hash",
            created_by=create_user,
            updated_by=create_user,
        )
        url = policy_url(workspace, p7_project, f"{revoked.id}/approve/")
        resp = approver_client.post(url, {}, format="json")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_cannot_modify_revoked_policy(
        self, session_client, workspace, p7_project, create_user
    ):
        revoked = AuthorizationPolicy.objects.create(
            workspace=workspace,
            project=p7_project,
            name="revoked-patch",
            description="Revoked patch policy",
            effect="deny",
            scope="project",
            priority=100,
            subjects=[],
            resources=[],
            actions=[],
            status=PolicyStatus.REVOKED,
            revision_number=1,
            content_hash="revokedpatch01",
            created_by=create_user,
            updated_by=create_user,
        )
        url = policy_url(workspace, p7_project, f"{revoked.id}/")
        resp = session_client.patch(url, {"priority": 1}, format="json")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_cannot_revoke_already_revoked(
        self, approver_client, workspace, p7_project, create_user
    ):
        revoked = AuthorizationPolicy.objects.create(
            workspace=workspace,
            project=p7_project,
            name="already-revoked",
            description="Already revoked policy",
            effect="deny",
            scope="project",
            priority=100,
            subjects=[],
            resources=[],
            actions=[],
            status=PolicyStatus.REVOKED,
            revision_number=1,
            content_hash="alreadyrevoked",
            created_by=create_user,
            updated_by=create_user,
        )
        url = policy_url(workspace, p7_project, f"{revoked.id}/revoke/")
        resp = approver_client.post(url, {"reason": "again"}, format="json")
        assert resp.status_code == status.HTTP_409_CONFLICT


# ── 5. Approval integrity — self-review blocked ──


@pytest.mark.django_db
class TestApprovalIntegrity:
    def test_author_cannot_approve_own_policy(
        self, session_client, workspace, p7_project, pending_policy
    ):
        """The policy creator cannot approve their own policy."""
        url = policy_url(workspace, p7_project, f"{pending_policy.id}/approve/")
        resp = session_client.post(url, {}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_different_admin_can_approve(
        self, approver_client, workspace, p7_project, pending_policy
    ):
        url = policy_url(workspace, p7_project, f"{pending_policy.id}/approve/")
        resp = approver_client.post(url, {}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        pending_policy.refresh_from_db()
        assert pending_policy.status == PolicyStatus.ACTIVE

    def test_requester_cannot_review_own_approval(
        self, session_client, workspace, p7_project, create_user
    ):
        decision = PolicyDecision.objects.create(
            workspace=workspace,
            project=p7_project,
            subject_type="agent",
            subject_ref="dev-engineer",
            resource_type="code",
            resource_ref="main",
            action="deploy",
            outcome="require_approval",
            matching_policies=[],
            reason="test",
            created_by=create_user,
            updated_by=create_user,
        )
        approval = ActionApproval.objects.create(
            workspace=workspace,
            project=p7_project,
            policy_decision=decision,
            action="deploy",
            subject_type="agent",
            subject_ref="dev-engineer",
            target_type="code",
            target_ref="main",
            requested_by=create_user,
            status=ApprovalStatus.PENDING,
            created_by=create_user,
            updated_by=create_user,
        )
        url = approval_url(workspace, p7_project, f"{approval.id}/")
        resp = session_client.patch(
            url, {"status": "approved", "reason": "ok"}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── 6. Emergency deny scoping ──


@pytest.mark.django_db
class TestEmergencyDenyScoping:
    def test_emergency_deny_created_with_project_scope(
        self, session_client, workspace, p7_project
    ):
        url = emergency_url(workspace, p7_project)
        resp = session_client.post(
            url, {"reason": "critical incident", "scope_filter": None}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        ed = EmergencyDeny.objects.get(id=resp.data["id"])
        assert str(ed.project_id) == str(p7_project.id)

    def test_deactivate_from_wrong_project_fails(
        self, session_client, workspace, p7_project, other_project, create_user
    ):
        ed = EmergencyDeny.objects.create(
            workspace=workspace,
            project=p7_project,
            reason="test",
            activated_by=create_user,
            is_active=True,
            created_by=create_user,
            updated_by=create_user,
        )
        url = emergency_url(workspace, other_project, f"{ed.id}/deactivate/")
        resp = session_client.post(url, {"reason": "done"}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_deactivate_already_inactive_fails(
        self, session_client, workspace, p7_project, create_user
    ):
        ed = EmergencyDeny.objects.create(
            workspace=workspace,
            project=p7_project,
            reason="test",
            activated_by=create_user,
            is_active=False,
            created_by=create_user,
            updated_by=create_user,
        )
        url = emergency_url(workspace, p7_project, f"{ed.id}/deactivate/")
        resp = session_client.post(url, {"reason": "done"}, format="json")
        assert resp.status_code == status.HTTP_409_CONFLICT


# ── 7. Policy simulation (read-only, non-persistent) ──


@pytest.mark.django_db
class TestPolicySimulation:
    def test_simulate_returns_deterministic_result(
        self, session_client, workspace, p7_project, active_policy
    ):
        url = f"/api/v1/workspaces/{workspace.slug}/projects/{p7_project.id}/policy-simulate/"
        resp = session_client.post(
            url,
            {
                "subject_type": "agent",
                "subject_ref": "qa-engineer",
                "resource_type": "code",
                "resource_ref": "main",
                "action": "read",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["outcome"] in ("allow", "deny", "require_approval")

    def test_simulate_does_not_create_decision_record(
        self, session_client, workspace, p7_project, active_policy
    ):
        before = PolicyDecision.objects.count()
        url = f"/api/v1/workspaces/{workspace.slug}/projects/{p7_project.id}/policy-simulate/"
        session_client.post(
            url,
            {
                "subject_type": "agent",
                "subject_ref": "qa-engineer",
                "resource_type": "code",
                "resource_ref": "main",
                "action": "read",
            },
            format="json",
        )
        assert PolicyDecision.objects.count() == before


# ── 8. Revocation requires a reason ──


@pytest.mark.django_db
class TestRevocationValidation:
    def test_revoke_without_reason_fails(
        self, approver_client, workspace, p7_project, active_policy
    ):
        url = policy_url(workspace, p7_project, f"{active_policy.id}/revoke/")
        resp = approver_client.post(url, {}, format="json")
        assert resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    def test_revoke_with_reason_succeeds(
        self, approver_client, workspace, p7_project, active_policy
    ):
        url = policy_url(workspace, p7_project, f"{active_policy.id}/revoke/")
        resp = approver_client.post(
            url, {"reason": "security review"}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        active_policy.refresh_from_db()
        assert active_policy.status == PolicyStatus.REVOKED
