# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraAttentionItem,
    AgentRun,
    ArtifactReference,
    AuthorizingReview,
    CatalogRevision,
    CompatibilityRecord,
    ContextManifest,
    EnvironmentRevision,
    IntegrationRegistration,
    KnowledgeConflict,
    KnowledgeIndexRecord,
    KnowledgeSource,
    KnowledgeVersion,
    ModelRoutingConfig,
    ProgressionOutcome,
    ProjectAgentEnablement,
    ReviewDisposition,
    VersionStatus,
    validate_version_status_transition,
    ActionApproval,
    ApprovalStatus,
    AuthorizationPolicy,
    EmergencyDeny,
    PolicyDecision,
    PolicyStatus,
    SeparationOfDutyConstraint,
)
from plane.agent_infra.services.assignment_queue import validate_status_transition
from plane.agent_infra.services.attention_enrichment import enrich_attention_item_details
from plane.api.serializers.base import BaseSerializer


class AgentAssignmentSerializer(BaseSerializer):
    class Meta:
        model = AgentAssignment
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_status(self, value):
        if self.instance and self.instance.status != value:
            try:
                validate_status_transition(self.instance.status, value)
            except DjangoValidationError as exc:
                messages = exc.message_dict.get("status", exc.messages)
                raise serializers.ValidationError(messages)
        return value


class AgentRunSerializer(BaseSerializer):
    class Meta:
        model = AgentRun
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "assignment",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class AuthorizingReviewSerializer(BaseSerializer):
    class Meta:
        model = AuthorizingReview
        fields = "__all__"
        read_only_fields = [
            "id",
            "run",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        run = attrs.get("run") or getattr(self.instance, "run", None) or self.context.get("run")
        reviewer_model = attrs.get("reviewer_model") or getattr(self.instance, "reviewer_model", None)

        if run and reviewer_model and reviewer_model == run.model_used:
            raise serializers.ValidationError(
                {"reviewer_model": "Reviewer model must differ from the agent run model."}
            )

        return attrs


class ArtifactReferenceSerializer(BaseSerializer):
    class Meta:
        model = ArtifactReference
        fields = "__all__"
        read_only_fields = [
            "id",
            "run",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class ReviewDispositionSerializer(BaseSerializer):
    class Meta:
        model = ReviewDisposition
        fields = "__all__"
        read_only_fields = [
            "id",
            "run",
            "reviewer",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class AgentCatalogSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False, allow_null=True)
    last_refreshed = serializers.CharField(required=False, allow_null=True)
    agents = serializers.ListField(child=serializers.DictField(), required=False)
    skills = serializers.ListField(child=serializers.DictField(), required=False)
    models = serializers.ListField(child=serializers.DictField(), required=False)
    environments = serializers.ListField(child=serializers.DictField(), required=False)
    integrations = serializers.ListField(child=serializers.DictField(), required=False)


class AgentCatalogSectionSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False, allow_null=True)
    last_refreshed = serializers.CharField(required=False, allow_null=True)
    items = serializers.ListField(child=serializers.DictField(), required=False)


class AgentInfraAttentionItemSerializer(BaseSerializer):
    details = serializers.SerializerMethodField()

    class Meta:
        model = AgentInfraAttentionItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "entity_type",
            "entity_id",
            "drift_type",
            "details",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_details(self, obj):
        cache = self.context.get("attention_enrichment_cache")
        if cache is not None:
            return cache.get(str(obj.id), enrich_attention_item_details(obj))
        return enrich_attention_item_details(obj)


class AgentSyncStatusSerializer(serializers.Serializer):
    pending_outbox_count = serializers.IntegerField()
    last_outbox_delivery_at = serializers.DateTimeField(allow_null=True)
    stale_assignment_count = serializers.IntegerField()
    orphaned_run_count = serializers.IntegerField()
    last_reconciliation_at = serializers.DateTimeField(allow_null=True)


class AgentRunDetailSerializer(BaseSerializer):
    """Enriched run detail returning all four authority layers in one response."""

    authorizing_review = AuthorizingReviewSerializer(read_only=True)
    review_disposition = ReviewDispositionSerializer(read_only=True)
    artifact_references = ArtifactReferenceSerializer(many=True, read_only=True)
    context_manifests = serializers.SerializerMethodField()
    assignment_summary = serializers.SerializerMethodField()

    class Meta:
        model = AgentRun
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "assignment",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_context_manifests(self, obj):
        return [
            {
                "id": str(m.id),
                "knowledge_version_id": str(m.knowledge_version_id),
                "source_name": m.knowledge_version.source.name if m.knowledge_version.source else None,
                "version_number": m.knowledge_version.version_number,
                "bound_at": m.bound_at.isoformat() if m.bound_at else None,
            }
            for m in obj.context_manifests.all()
        ]

    def get_assignment_summary(self, obj):
        a = obj.assignment
        return {
            "id": str(a.id),
            "agent_ref": a.agent_ref,
            "assignment_type": a.assignment_type,
            "status": a.status,
            "work_item_id": str(a.work_item_id) if a.work_item_id else None,
        }


class RunProgressionSerializer(serializers.Serializer):
    """Validates DC-reported progression outcome."""

    progression_outcome = serializers.ChoiceField(choices=ProgressionOutcome.choices)
    progression_reason = serializers.CharField(required=False, allow_blank=True, default="")


class AgentRunLedgerSerializer(BaseSerializer):
    """Lightweight run serializer for the project-wide run ledger."""

    verdict = serializers.SerializerMethodField()
    disposition = serializers.SerializerMethodField()
    work_item_id = serializers.SerializerMethodField()

    class Meta:
        model = AgentRun
        fields = [
            "id",
            "agent_ref",
            "model_used",
            "outcome",
            "progression_outcome",
            "started_at",
            "completed_at",
            "tokens_in",
            "tokens_out",
            "cost_usd",
            "correlation_id",
            "verdict",
            "disposition",
            "work_item_id",
            "assignment",
            "created_at",
        ]

    def get_verdict(self, obj):
        review = getattr(obj, "_prefetched_review", None)
        if review is None:
            try:
                review = obj.authorizing_review
            except AuthorizingReview.DoesNotExist:
                return None
        return review.verdict if review else None

    def get_disposition(self, obj):
        disposition = getattr(obj, "_prefetched_disposition", None)
        if disposition is None:
            try:
                disposition = obj.review_disposition
            except ReviewDisposition.DoesNotExist:
                return None
        return disposition.disposition if disposition else None

    def get_work_item_id(self, obj):
        return str(obj.assignment.work_item_id) if obj.assignment_id else None


class KnowledgeSourceSerializer(BaseSerializer):
    class Meta:
        model = KnowledgeSource
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "is_retired",
            "retired_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class KnowledgeVersionSerializer(BaseSerializer):
    class Meta:
        model = KnowledgeVersion
        fields = "__all__"
        read_only_fields = [
            "id",
            "source",
            "workspace",
            "project",
            "version_number",
            "promoted_by",
            "promoted_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_status(self, value):
        if self.instance and self.instance.status != value:
            try:
                validate_version_status_transition(
                    self.instance.status,
                    value,
                    is_agent_generated=self.instance.is_agent_generated,
                )
            except DjangoValidationError as exc:
                messages = exc.message_dict.get("status", exc.messages)
                raise serializers.ValidationError(messages)
        return value

    def validate(self, attrs):
        is_agent_generated = attrs.get(
            "is_agent_generated",
            getattr(self.instance, "is_agent_generated", False),
        )
        status = attrs.get("status", getattr(self.instance, "status", VersionStatus.DRAFT))

        if self.instance is None and is_agent_generated and status != VersionStatus.QUARANTINED:
            raise serializers.ValidationError(
                {
                    "status": (
                        "Agent-generated knowledge versions must enter with "
                        "status 'quarantined'."
                    )
                }
            )
        return attrs


class ContextManifestSerializer(BaseSerializer):
    class Meta:
        model = ContextManifest
        fields = "__all__"
        read_only_fields = [
            "id",
            "run",
            "knowledge_version",
            "workspace",
            "project",
            "bound_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class KnowledgeIndexRecordSerializer(BaseSerializer):
    class Meta:
        model = KnowledgeIndexRecord
        fields = "__all__"
        read_only_fields = [
            "id",
            "knowledge_version",
            "action",
            "workspace",
            "project",
            "requested_at",
            "acknowledged_at",
            "completed_at",
            "failed_at",
            "retry_count",
            "is_verified",
            "last_observed_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class ProjectAgentEnablementSerializer(BaseSerializer):
    class Meta:
        model = ProjectAgentEnablement
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "enabled_by",
            "enabled_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class ModelRoutingConfigSerializer(BaseSerializer):
    class Meta:
        model = ModelRoutingConfig
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "budget_used_usd",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class KnowledgeConflictSerializer(BaseSerializer):
    class Meta:
        model = KnowledgeConflict
        fields = "__all__"
        read_only_fields = [
            "version_a",
            "version_b",
            "id",
            "workspace",
            "project",
            "resolved_by",
            "resolved_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        workspace_id = self.context.get("workspace_id")
        project_id = self.context.get("project_id")

        for field in ("version_a", "version_b", "winning_version"):
            version = attrs.get(field)
            if version and (
                version.project_id != project_id or version.workspace_id != workspace_id
            ):
                raise serializers.ValidationError(
                    {field: "Version does not belong to this project"}
                )

        version_a = attrs.get("version_a", getattr(self.instance, "version_a", None))
        version_b = attrs.get("version_b", getattr(self.instance, "version_b", None))
        winning = attrs.get("winning_version", getattr(self.instance, "winning_version", None))

        if version_a and version_b and version_a.id == version_b.id:
            raise serializers.ValidationError(
                {"version_b": "Must differ from version_a"}
            )

        if winning and version_a and version_b:
            if winning.id not in (version_a.id, version_b.id):
                raise serializers.ValidationError(
                    {"winning_version": "Must be one of the conflicting versions"}
                )

        return attrs


class EnvironmentRevisionSerializer(BaseSerializer):
    class Meta:
        model = EnvironmentRevision
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "revision_number",
            "drift_status",
            "drift_detail",
            "last_drift_check_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class IntegrationRegistrationSerializer(BaseSerializer):
    class Meta:
        model = IntegrationRegistration
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class CatalogRevisionSerializer(BaseSerializer):
    class Meta:
        model = CatalogRevision
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "revision_number",
            "status",
            "diff_summary",
            "approved_by",
            "approved_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class CompatibilityRecordSerializer(BaseSerializer):
    class Meta:
        model = CompatibilityRecord
        fields = "__all__"
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "last_checked_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


# ── P7: Authorization Policy Serializers ──


class AuthorizationPolicySerializer(BaseSerializer):
    class Meta:
        model = AuthorizationPolicy
        fields = "__all__"
        read_only_fields = [
            "id", "created_at", "updated_at", "created_by", "updated_by",
            "workspace", "project", "previous_revision",
            "approved_by", "approved_at", "revoked_by", "revoked_at",
            "revocation_reason", "content_hash", "revision_number",
        ]

    def validate_subjects(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("subjects must be a list")
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each subject must be an object")
            if "type" not in item or "ref" not in item:
                raise serializers.ValidationError("Each subject must have 'type' and 'ref' fields")
        return value

    def validate_resources(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("resources must be a list")
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each resource must be an object")
            if "type" not in item or "ref" not in item:
                raise serializers.ValidationError("Each resource must have 'type' and 'ref' fields")
        return value

    def validate_actions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("actions must be a list")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Each action must be a string")
        return value

    def validate_conditions(self, value):
        if value is None:
            return value
        if not isinstance(value, list):
            raise serializers.ValidationError("conditions must be a list of condition objects or null")
        for condition in value:
            if not isinstance(condition, dict):
                raise serializers.ValidationError("Each condition must be an object")
            if "field" not in condition:
                raise serializers.ValidationError("Each condition must have a 'field' key")
            if "value" not in condition:
                raise serializers.ValidationError("Each condition must have a 'value' key")
        return value

    def validate_separation_of_duty(self, value):
        if value is None:
            return value
        if not isinstance(value, list):
            raise serializers.ValidationError("separation_of_duty must be a list or null")
        for rule in value:
            if not isinstance(rule, dict):
                raise serializers.ValidationError("Each SoD rule must be an object")
            if "name" not in rule or "conflicting_actions" not in rule:
                raise serializers.ValidationError(
                    "Each SoD rule must have 'name' and 'conflicting_actions'"
                )
            if not isinstance(rule["conflicting_actions"], list):
                raise serializers.ValidationError("conflicting_actions must be a list")
            if len(rule["conflicting_actions"]) < 2:
                raise serializers.ValidationError(
                    "conflicting_actions must contain at least 2 actions"
                )
        return value

    def validate(self, data):
        emergency = data.get("emergency", getattr(self.instance, "emergency", False))
        effect = data.get("effect", getattr(self.instance, "effect", None))
        priority = data.get("priority", getattr(self.instance, "priority", 100))
        if emergency:
            if effect != "deny":
                raise serializers.ValidationError(
                    {"effect": "Emergency policies must have effect 'deny'."}
                )
            if priority != 0:
                raise serializers.ValidationError(
                    {"priority": "Emergency policies must have priority 0."}
                )
        return data


class AuthorizationPolicyListSerializer(BaseSerializer):
    class Meta:
        model = AuthorizationPolicy
        fields = [
            "id", "name", "version", "description", "scope", "priority",
            "effect", "status", "autonomy_classification", "emergency",
            "revision_number", "expires_at", "owner", "created_at", "updated_at",
        ]


class ActionApprovalSerializer(BaseSerializer):
    class Meta:
        model = ActionApproval
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class ActionApprovalReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class EmergencyDenySerializer(BaseSerializer):
    class Meta:
        model = EmergencyDeny
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class EmergencyDenyActivateSerializer(serializers.Serializer):
    reason = serializers.CharField()
    scope_filter = serializers.JSONField(required=False, allow_null=True, default=None)
    incident_reference = serializers.CharField(required=False, allow_blank=True, default="")


class EmergencyDenyDeactivateSerializer(serializers.Serializer):
    reason = serializers.CharField()


class PolicyDecisionSerializer(BaseSerializer):
    class Meta:
        model = PolicyDecision
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class SeparationOfDutyConstraintSerializer(BaseSerializer):
    class Meta:
        model = SeparationOfDutyConstraint
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class PolicySimulateSerializer(serializers.Serializer):
    subject_type = serializers.CharField()
    subject_ref = serializers.CharField()
    resource_type = serializers.CharField()
    resource_ref = serializers.CharField()
    action = serializers.CharField()
    context = serializers.JSONField(required=False, default=dict)
    correlation_id = serializers.CharField(required=False, allow_blank=True, default="")


class PolicyDiffSerializer(serializers.Serializer):
    compare_with = serializers.UUIDField()


class PolicyBlastRadiusSerializer(serializers.Serializer):
    pass
