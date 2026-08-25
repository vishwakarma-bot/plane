# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""P7: Authorization policy API views.

Provides:
- Policy CRUD with versioning (draft → pending_approval → active)
- Policy simulation (dry-run evaluation)
- Policy diff and blast-radius analysis
- Exact-action approval queue management
- Emergency deny activation/deactivation
- Separation-of-duty constraint management
- Policy decision history
"""

import hashlib
import json

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from plane.agent_infra.error_format import (
    APPROVAL_EXPIRED,
    APPROVAL_REQUIRED,
    EMERGENCY_DENY_ACTIVE,
    FORBIDDEN,
    INVALID_STATUS_TRANSITION,
    NOT_FOUND,
    POLICY_ALREADY_ACTIVE,
    POLICY_NOT_FOUND,
    POLICY_VIOLATION,
    SEPARATION_OF_DUTY_VIOLATION,
    agent_infra_error_response,
    agent_infra_validation_error_response,
)
from plane.agent_infra.mixins import AgentInfraFeatureFlagMixin
from plane.agent_infra.models import (
    ActionApproval,
    ApprovalStatus,
    AuthorizationPolicy,
    EmergencyDeny,
    PolicyDecision,
    PolicyStatus,
    SeparationOfDutyConstraint,
)
from plane.agent_infra.services.policy_evaluator import EvaluationRequest, PolicyEvaluator
from plane.api.serializers.agent_infra import (
    ActionApprovalReviewSerializer,
    ActionApprovalSerializer,
    AuthorizationPolicyListSerializer,
    AuthorizationPolicySerializer,
    EmergencyDenyActivateSerializer,
    EmergencyDenyDeactivateSerializer,
    EmergencyDenySerializer,
    PolicyBlastRadiusSerializer,
    PolicyDecisionSerializer,
    PolicyDiffSerializer,
    PolicySimulateSerializer,
    SeparationOfDutyConstraintSerializer,
)
from plane.app.permissions import ProjectAdminPermission, ProjectEntityPermission
from plane.api.views.base import BaseAPIView


# --- Authorization Policy CRUD ---


class AuthorizationPolicyListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AuthorizationPolicySerializer
    model = AuthorizationPolicy
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return AuthorizationPolicy.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
        ).filter(
            Q(project_id=self.kwargs.get("project_id")) | Q(project_id__isnull=True)
        ).order_by("priority", "-revision_number")

    def get(self, request, slug, project_id):
        queryset = self.get_queryset()

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        effect_filter = request.query_params.get("effect")
        if effect_filter:
            queryset = queryset.filter(effect=effect_filter)

        scope_filter = request.query_params.get("scope")
        if scope_filter:
            queryset = queryset.filter(scope=scope_filter)

        emergency_filter = request.query_params.get("emergency")
        if emergency_filter is not None:
            queryset = queryset.filter(emergency=emergency_filter.lower() == "true")

        queryset = queryset[:200]

        serializer = AuthorizationPolicyListSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request, slug, project_id):
        workspace = self.get_workspace(slug)
        data = request.data.copy()
        data["status"] = PolicyStatus.DRAFT

        if data.get("scope") == "workspace":
            return agent_infra_error_response(
                POLICY_VIOLATION,
                "Workspace-scoped policies cannot be created on a project endpoint. "
                "Use scope='project' for project-level policies.",
                status.HTTP_400_BAD_REQUEST,
            )

        content_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        with transaction.atomic():
            from plane.db.models import Project
            Project.objects.select_for_update().filter(pk=project_id).first()

            last_revision = AuthorizationPolicy.objects.filter(
                workspace=workspace,
                name=data.get("name", ""),
            ).order_by("-revision_number").first()

            revision_number = (last_revision.revision_number + 1) if last_revision else 1

            serializer = AuthorizationPolicySerializer(data=data, context={"request": request})
            if not serializer.is_valid():
                return agent_infra_validation_error_response(serializer.errors, request)

            serializer.save(
                workspace=workspace,
                project_id=project_id,
                content_hash=content_hash,
                revision_number=revision_number,
                previous_revision=last_revision,
                created_by=request.user,
                updated_by=request.user,
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_workspace(self, slug):
        from plane.db.models import Workspace
        return Workspace.objects.get(slug=slug)


class AuthorizationPolicyDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AuthorizationPolicySerializer
    model = AuthorizationPolicy

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [ProjectEntityPermission()]
        return [ProjectAdminPermission()]

    def get_object(self):
        return AuthorizationPolicy.objects.get(
            id=self.kwargs.get("policy_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        )

    def get(self, request, slug, project_id, policy_id):
        try:
            policy = self.get_object()
        except AuthorizationPolicy.DoesNotExist:
            return agent_infra_error_response(
                POLICY_NOT_FOUND, "Policy not found", status.HTTP_404_NOT_FOUND
            )
        serializer = AuthorizationPolicySerializer(policy)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id, policy_id):
        with transaction.atomic():
            try:
                policy = AuthorizationPolicy.objects.select_for_update().get(
                    id=policy_id,
                    workspace__slug=slug,
                    project_id=project_id,
                )
            except AuthorizationPolicy.DoesNotExist:
                return agent_infra_error_response(
                    POLICY_NOT_FOUND, "Policy not found", status.HTTP_404_NOT_FOUND
                )

            if policy.status == PolicyStatus.REVOKED:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    "Cannot modify a revoked policy",
                    status.HTTP_409_CONFLICT,
                )

            new_status = request.data.get("status")
            if new_status == PolicyStatus.ACTIVE and policy.status != PolicyStatus.ACTIVE:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    "Policies can only be activated through the approval workflow",
                    status.HTTP_409_CONFLICT,
                )

            if policy.status in (PolicyStatus.ACTIVE, PolicyStatus.DEPRECATED):
                blocked_fields = {
                    "subjects",
                    "resources",
                    "actions",
                    "conditions",
                    "effect",
                    "priority",
                    "separation_of_duty",
                    "status",
                    "expires_at",
                    "autonomy_classification",
                    "scope",
                    "emergency",
                }.intersection(request.data.keys())
                if blocked_fields:
                    return agent_infra_error_response(
                        POLICY_VIOLATION,
                        f"Cannot modify enforcement fields on an {policy.status} policy: "
                        f"{', '.join(sorted(blocked_fields))}. Use the dedicated revocation workflow.",
                        status.HTTP_409_CONFLICT,
                    )

            serializer = AuthorizationPolicySerializer(
                policy, data=request.data, partial=True, context={"request": request}
            )
            if not serializer.is_valid():
                return agent_infra_validation_error_response(serializer.errors, request)

            serializer.save(updated_by=request.user)

        return Response(serializer.data, status=status.HTTP_200_OK)


class AuthorizationPolicyApproveAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Approve a pending_approval policy, transitioning it to active."""

    permission_classes = [ProjectAdminPermission]

    def post(self, request, slug, project_id, policy_id):
        with transaction.atomic():
            try:
                policy = AuthorizationPolicy.objects.select_for_update().get(
                    id=policy_id,
                    workspace__slug=slug,
                    project_id=project_id,
                )
            except AuthorizationPolicy.DoesNotExist:
                return agent_infra_error_response(
                    POLICY_NOT_FOUND, "Policy not found", status.HTTP_404_NOT_FOUND
                )

            if policy.status != PolicyStatus.PENDING_APPROVAL:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    f"Cannot approve a policy in status '{policy.status}'; must be pending_approval",
                    status.HTTP_409_CONFLICT,
                )

            if policy.created_by == request.user:
                return agent_infra_error_response(
                    SEPARATION_OF_DUTY_VIOLATION,
                    "Policy author cannot approve their own policy",
                    status.HTTP_403_FORBIDDEN,
                )

            policy.status = PolicyStatus.ACTIVE
            policy.approved_by = request.user
            policy.approved_at = timezone.now()
            policy.save()

            if policy.separation_of_duty:
                for rule in policy.separation_of_duty:
                    SeparationOfDutyConstraint.objects.get_or_create(
                        workspace=policy.workspace,
                        project=policy.project,
                        policy=policy,
                        name=rule.get("name"),
                        defaults={
                            "description": rule.get("description"),
                            "conflicting_actions": rule.get("conflicting_actions"),
                            "scope": rule.get("scope", "run"),
                            "is_active": True,
                            "created_by": request.user,
                            "updated_by": request.user,
                        },
                    )

        serializer = AuthorizationPolicySerializer(policy)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AuthorizationPolicyRevokeAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Revoke an active policy."""

    permission_classes = [ProjectAdminPermission]

    def post(self, request, slug, project_id, policy_id):
        with transaction.atomic():
            try:
                policy = AuthorizationPolicy.objects.select_for_update().get(
                    id=policy_id,
                    workspace__slug=slug,
                    project_id=project_id,
                )
            except AuthorizationPolicy.DoesNotExist:
                return agent_infra_error_response(
                    POLICY_NOT_FOUND, "Policy not found", status.HTTP_404_NOT_FOUND
                )

            if policy.status == PolicyStatus.REVOKED:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    "Policy is already revoked",
                    status.HTTP_409_CONFLICT,
                )

            reason = request.data.get("reason", "")
            if not reason:
                return agent_infra_validation_error_response(
                    {"reason": "Revocation reason is required"}, request
                )

            policy.status = PolicyStatus.REVOKED
            policy.revoked_by = request.user
            policy.revoked_at = timezone.now()
            policy.revocation_reason = reason
            policy.save()

            SeparationOfDutyConstraint.objects.filter(
                policy=policy
            ).update(is_active=False)

        serializer = AuthorizationPolicySerializer(policy)
        return Response(serializer.data, status=status.HTTP_200_OK)


# --- Policy Simulation ---


class PolicySimulateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Simulate policy evaluation without recording a decision."""

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id):
        serializer = PolicySimulateSerializer(data=request.data)
        if not serializer.is_valid():
            return agent_infra_validation_error_response(serializer.errors, request)

        from plane.db.models import Workspace
        workspace = Workspace.objects.get(slug=slug)

        eval_request = EvaluationRequest(
            workspace_id=workspace.id,
            project_id=project_id,
            subject_type=serializer.validated_data["subject_type"],
            subject_ref=serializer.validated_data["subject_ref"],
            resource_type=serializer.validated_data["resource_type"],
            resource_ref=serializer.validated_data["resource_ref"],
            action=serializer.validated_data["action"],
            context=serializer.validated_data.get("context", {}),
        )

        evaluator = PolicyEvaluator()
        result = evaluator.simulate(eval_request)

        return Response(
            {
                "outcome": result.outcome,
                "deciding_policy": str(result.deciding_policy_id) if result.deciding_policy_id else None,
                "reason": result.reason,
                "matching_policies": [
                    {
                        "id": str(m.policy_id),
                        "name": m.policy_name,
                        "priority": m.priority,
                        "effect": m.effect,
                    }
                    for m in result.matching_policies
                ],
                "sod_violations": [
                    {"constraint": v.split(":")[0].strip() if ":" in v else v, "description": v}
                    for v in result.separation_of_duty_violations
                ],
                "emergency_deny_active": result.emergency_deny_active,
            },
            status=status.HTTP_200_OK,
        )


# --- Policy Diff and Blast Radius ---


class PolicyDiffAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Compute semantic diff between two policy revisions."""

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id):
        serializer = PolicyDiffSerializer(data=request.data)
        if not serializer.is_valid():
            return agent_infra_validation_error_response(serializer.errors, request)

        from plane.db.models import Workspace
        workspace = Workspace.objects.get(slug=slug)

        evaluator = PolicyEvaluator()
        try:
            diff = evaluator.diff_policies(
                workspace_id=workspace.id,
                project_id=project_id,
                policy_a_id=serializer.validated_data["policy_a_id"],
                policy_b_id=serializer.validated_data["policy_b_id"],
            )
        except AuthorizationPolicy.DoesNotExist:
            return agent_infra_error_response(
                POLICY_NOT_FOUND, "One or both policies not found", status.HTTP_404_NOT_FOUND
            )

        return Response(diff, status=status.HTTP_200_OK)


class PolicyBlastRadiusAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Estimate blast radius of a policy."""

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id):
        serializer = PolicyBlastRadiusSerializer(data=request.data)
        if not serializer.is_valid():
            return agent_infra_validation_error_response(serializer.errors, request)

        from plane.db.models import Workspace
        workspace = Workspace.objects.get(slug=slug)

        evaluator = PolicyEvaluator()
        try:
            radius = evaluator.blast_radius(
                workspace_id=workspace.id,
                project_id=project_id,
                policy_id=serializer.validated_data["policy_id"],
            )
        except AuthorizationPolicy.DoesNotExist:
            return agent_infra_error_response(
                POLICY_NOT_FOUND, "Policy not found", status.HTTP_404_NOT_FOUND
            )

        return Response(radius, status=status.HTTP_200_OK)


# --- Policy Decision History ---


class PolicyDecisionListAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Read-only access to policy decision audit trail."""

    serializer_class = PolicyDecisionSerializer
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        queryset = PolicyDecision.objects.filter(
            workspace__slug=slug,
        ).filter(
            Q(project_id=project_id) | Q(project_id__isnull=True)
        ).order_by("-evaluated_at")

        outcome_filter = request.query_params.get("outcome")
        if outcome_filter:
            queryset = queryset.filter(outcome=outcome_filter)

        action_filter = request.query_params.get("action")
        if action_filter:
            queryset = queryset.filter(action=action_filter)

        subject_filter = request.query_params.get("subject_ref")
        if subject_filter:
            queryset = queryset.filter(subject_ref=subject_filter)

        queryset = queryset[:100]

        serializer = PolicyDecisionSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)


# --- Action Approval Queue ---


class ActionApprovalListAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """List pending and historical action approvals."""

    serializer_class = ActionApprovalSerializer
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        queryset = ActionApproval.objects.filter(
            workspace__slug=slug,
        ).filter(
            Q(project_id=project_id) | Q(project_id__isnull=True)
        ).order_by("-created_at")

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            queryset = queryset.filter(status=ApprovalStatus.PENDING)

        queryset = queryset[:100]
        serializer = ActionApprovalSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)


class ActionApprovalDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Review (approve/reject) an action approval."""

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [ProjectEntityPermission()]
        return [ProjectAdminPermission()]

    def get(self, request, slug, project_id, approval_id):
        try:
            approval = ActionApproval.objects.get(
                id=approval_id,
                workspace__slug=slug,
                project_id=project_id,
            )
        except ActionApproval.DoesNotExist:
            return agent_infra_error_response(
                NOT_FOUND, "Approval not found", status.HTTP_404_NOT_FOUND
            )
        serializer = ActionApprovalSerializer(approval)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id, approval_id):
        """Review an approval: approve or reject."""
        with transaction.atomic():
            try:
                approval = ActionApproval.objects.select_for_update().get(
                    id=approval_id,
                    workspace__slug=slug,
                    project_id=project_id,
                )
            except ActionApproval.DoesNotExist:
                return agent_infra_error_response(
                    NOT_FOUND, "Approval not found", status.HTTP_404_NOT_FOUND
                )

            if approval.status != ApprovalStatus.PENDING:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    f"Approval is already in status '{approval.status}'",
                    status.HTTP_409_CONFLICT,
                )

            if approval.is_expired:
                approval.status = ApprovalStatus.EXPIRED
                approval.save()
                return agent_infra_error_response(
                    APPROVAL_EXPIRED,
                    "This approval has expired",
                    status.HTTP_410_GONE,
                )

            if approval.requested_by == request.user:
                return agent_infra_error_response(
                    SEPARATION_OF_DUTY_VIOLATION,
                    "Requester cannot review their own approval",
                    status.HTTP_403_FORBIDDEN,
                )

            review_serializer = ActionApprovalReviewSerializer(data=request.data)
            if not review_serializer.is_valid():
                return agent_infra_validation_error_response(review_serializer.errors, request)

            new_status = review_serializer.validated_data["status"]

            if new_status == ApprovalStatus.APPROVED:
                sod_violation = self._recheck_sod_on_approve(approval)
                if sod_violation:
                    return agent_infra_error_response(
                        SEPARATION_OF_DUTY_VIOLATION,
                        sod_violation,
                        status.HTTP_409_CONFLICT,
                    )

            approval.status = new_status
            approval.reviewed_by = request.user
            approval.reviewed_at = timezone.now()
            approval.review_reason = review_serializer.validated_data.get("reason", "")
            approval.save()

        serializer = ActionApprovalSerializer(approval)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _recheck_sod_on_approve(self, approval) -> str | None:
        """Recheck SoD constraints before approving, under the same locks."""
        constraints = SeparationOfDutyConstraint.objects.select_for_update().filter(
            workspace_id=approval.workspace_id,
            is_active=True,
        )
        if approval.project_id:
            constraints = constraints.filter(
                Q(project_id=approval.project_id) | Q(project_id__isnull=True)
            )

        for constraint in constraints:
            if approval.action not in constraint.conflicting_actions:
                continue

            other_actions = [
                a for a in constraint.conflicting_actions if a != approval.action
            ]

            scope_filter = {"workspace_id": approval.workspace_id}
            decision = approval.policy_decision
            if constraint.scope == "run" and decision.run_id:
                scope_filter["run_id"] = decision.run_id
            elif constraint.scope == "assignment" and decision.correlation_id:
                scope_filter["correlation_id"] = decision.correlation_id
            elif constraint.scope == "project" and approval.project_id:
                scope_filter["project_id"] = approval.project_id
            else:
                continue

            conflict_exists = PolicyDecision.objects.filter(
                subject_type=approval.subject_type,
                subject_ref=approval.subject_ref,
                action__in=other_actions,
                outcome="allow",
                **scope_filter,
            ).exists()

            if not conflict_exists:
                conflict_exists = PolicyDecision.objects.filter(
                    subject_type=approval.subject_type,
                    subject_ref=approval.subject_ref,
                    action__in=other_actions,
                    outcome="require_approval",
                    approval_requests__status=ApprovalStatus.APPROVED,
                    **scope_filter,
                ).exists()

            if conflict_exists:
                return (
                    f"Cannot approve: SoD constraint '{constraint.name}' violated — "
                    f"actor {approval.subject_ref} already performed "
                    f"{other_actions} in this {constraint.scope}"
                )

        return None


# --- Emergency Deny ---


class EmergencyDenyListAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """List and create emergency denies."""

    serializer_class = EmergencyDenySerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [ProjectEntityPermission()]
        return [ProjectAdminPermission()]

    def get(self, request, slug, project_id):
        queryset = EmergencyDeny.objects.filter(
            workspace__slug=slug,
        ).filter(
            Q(project_id=project_id) | Q(project_id__isnull=True)
        ).order_by("-activated_at")

        active_filter = request.query_params.get("active")
        if active_filter is not None:
            queryset = queryset.filter(is_active=active_filter.lower() == "true")

        queryset = queryset[:100]

        serializer = EmergencyDenySerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request, slug, project_id):
        serializer = EmergencyDenyActivateSerializer(data=request.data)
        if not serializer.is_valid():
            return agent_infra_validation_error_response(serializer.errors, request)

        from plane.db.models import Workspace
        workspace = Workspace.objects.get(slug=slug)

        with transaction.atomic():
            emergency = EmergencyDeny.objects.create(
                workspace=workspace,
                project_id=project_id,
                reason=serializer.validated_data["reason"],
                scope_filter=serializer.validated_data.get("scope_filter"),
                incident_reference=serializer.validated_data.get("incident_reference", ""),
                activated_by=request.user,
                is_active=True,
                created_by=request.user,
                updated_by=request.user,
            )

        result_serializer = EmergencyDenySerializer(emergency)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)


class EmergencyDenyActivateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Activate a new emergency deny, scoped to the URL's project."""

    permission_classes = [ProjectAdminPermission]

    def post(self, request, slug, project_id):
        serializer = EmergencyDenyActivateSerializer(data=request.data)
        if not serializer.is_valid():
            return agent_infra_validation_error_response(serializer.errors, request)

        from plane.db.models import Workspace
        workspace = Workspace.objects.get(slug=slug)

        with transaction.atomic():
            emergency = EmergencyDeny.objects.create(
                workspace=workspace,
                project_id=project_id,
                reason=serializer.validated_data["reason"],
                scope_filter=serializer.validated_data.get("scope_filter"),
                incident_reference=serializer.validated_data.get("incident_reference", ""),
                activated_by=request.user,
                is_active=True,
                created_by=request.user,
                updated_by=request.user,
            )

        result_serializer = EmergencyDenySerializer(emergency)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)


class EmergencyDenyDeactivateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Deactivate an emergency deny."""

    permission_classes = [ProjectAdminPermission]

    def post(self, request, slug, project_id, emergency_id):
        with transaction.atomic():
            try:
                emergency = EmergencyDeny.objects.select_for_update().get(
                    id=emergency_id,
                    workspace__slug=slug,
                    project_id=project_id,
                )
            except EmergencyDeny.DoesNotExist:
                return agent_infra_error_response(
                    NOT_FOUND, "Emergency deny not found", status.HTTP_404_NOT_FOUND
                )

            if not emergency.is_active:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    "Emergency deny is already deactivated",
                    status.HTTP_409_CONFLICT,
                )

            deactivate_serializer = EmergencyDenyDeactivateSerializer(data=request.data)
            if not deactivate_serializer.is_valid():
                return agent_infra_validation_error_response(deactivate_serializer.errors, request)

            emergency.is_active = False
            emergency.deactivated_by = request.user
            emergency.deactivated_at = timezone.now()
            emergency.deactivation_reason = deactivate_serializer.validated_data["reason"]
            emergency.save()

        serializer = EmergencyDenySerializer(emergency)
        return Response(serializer.data, status=status.HTTP_200_OK)


# --- Separation of Duty Constraints ---


class SeparationOfDutyListAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """List active separation-of-duty constraints."""

    serializer_class = SeparationOfDutyConstraintSerializer
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        queryset = SeparationOfDutyConstraint.objects.filter(
            workspace__slug=slug,
        ).filter(
            Q(project_id=project_id) | Q(project_id__isnull=True)
        ).filter(is_active=True).order_by("name")

        queryset = queryset[:200]

        serializer = SeparationOfDutyConstraintSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)
