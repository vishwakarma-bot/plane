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
from plane.app.permissions import ProjectEntityPermission
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

        serializer = AuthorizationPolicyListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, slug, project_id):
        workspace = self.get_workspace(slug)
        data = request.data.copy()

        content_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        with transaction.atomic():
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
    permission_classes = [ProjectEntityPermission]

    def get_object(self):
        return AuthorizationPolicy.objects.get(
            id=self.kwargs.get("policy_id"),
            workspace__slug=self.kwargs.get("slug"),
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
        try:
            policy = self.get_object()
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

        serializer = AuthorizationPolicySerializer(
            policy, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return agent_infra_validation_error_response(serializer.errors, request)

        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AuthorizationPolicyApproveAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Approve a pending_approval policy, transitioning it to active."""

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id, policy_id):
        try:
            policy = AuthorizationPolicy.objects.select_for_update().get(
                id=policy_id,
                workspace__slug=slug,
            )
        except AuthorizationPolicy.DoesNotExist:
            return agent_infra_error_response(
                POLICY_NOT_FOUND, "Policy not found", status.HTTP_404_NOT_FOUND
            )

        if policy.status not in (PolicyStatus.PENDING_APPROVAL, PolicyStatus.DRAFT):
            return agent_infra_error_response(
                INVALID_STATUS_TRANSITION,
                f"Cannot approve a policy in status '{policy.status}'",
                status.HTTP_409_CONFLICT,
            )

        if policy.created_by == request.user:
            return agent_infra_error_response(
                SEPARATION_OF_DUTY_VIOLATION,
                "Policy author cannot approve their own policy",
                status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
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

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id, policy_id):
        try:
            policy = AuthorizationPolicy.objects.select_for_update().get(
                id=policy_id,
                workspace__slug=slug,
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

        with transaction.atomic():
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
                "deciding_policy_id": str(result.deciding_policy_id) if result.deciding_policy_id else None,
                "deciding_policy_name": result.deciding_policy_name,
                "reason": result.reason,
                "matching_policies": [
                    {
                        "policy_id": str(m.policy_id),
                        "policy_name": m.policy_name,
                        "priority": m.priority,
                        "effect": m.effect,
                        "match_reason": m.match_reason,
                    }
                    for m in result.matching_policies
                ],
                "separation_of_duty_violations": result.separation_of_duty_violations,
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
        return Response(serializer.data, status=status.HTTP_200_OK)


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
        return Response(serializer.data, status=status.HTTP_200_OK)


class ActionApprovalDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Review (approve/reject) an action approval."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, approval_id):
        try:
            approval = ActionApproval.objects.get(
                id=approval_id,
                workspace__slug=slug,
            )
        except ActionApproval.DoesNotExist:
            return agent_infra_error_response(
                NOT_FOUND, "Approval not found", status.HTTP_404_NOT_FOUND
            )
        serializer = ActionApprovalSerializer(approval)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id, approval_id):
        """Review an approval: approve or reject."""
        try:
            approval = ActionApproval.objects.select_for_update().get(
                id=approval_id,
                workspace__slug=slug,
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

        with transaction.atomic():
            approval.status = review_serializer.validated_data["status"]
            approval.reviewed_by = request.user
            approval.reviewed_at = timezone.now()
            approval.review_reason = review_serializer.validated_data.get("reason", "")
            approval.save()

        serializer = ActionApprovalSerializer(approval)
        return Response(serializer.data, status=status.HTTP_200_OK)


# --- Emergency Deny ---


class EmergencyDenyListAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """List emergency denies (active and historical)."""

    serializer_class = EmergencyDenySerializer
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        queryset = EmergencyDeny.objects.filter(
            workspace__slug=slug,
        ).order_by("-activated_at")

        active_filter = request.query_params.get("active")
        if active_filter is not None:
            queryset = queryset.filter(is_active=active_filter.lower() == "true")

        serializer = EmergencyDenySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EmergencyDenyActivateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Activate a new emergency deny."""

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id):
        serializer = EmergencyDenyActivateSerializer(data=request.data)
        if not serializer.is_valid():
            return agent_infra_validation_error_response(serializer.errors, request)

        from plane.db.models import Workspace
        workspace = Workspace.objects.get(slug=slug)

        with transaction.atomic():
            emergency = EmergencyDeny.objects.create(
                workspace=workspace,
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

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id, emergency_id):
        try:
            emergency = EmergencyDeny.objects.select_for_update().get(
                id=emergency_id,
                workspace__slug=slug,
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

        with transaction.atomic():
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

        serializer = SeparationOfDutyConstraintSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
