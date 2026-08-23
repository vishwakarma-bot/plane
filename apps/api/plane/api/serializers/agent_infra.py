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
    KnowledgeSource,
    KnowledgeVersion,
    ModelRoutingConfig,
    ProjectAgentEnablement,
    ReviewDisposition,
    VersionStatus,
    validate_version_status_transition,
)
from plane.agent_infra.services.assignment_queue import validate_status_transition
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


class AgentSyncStatusSerializer(serializers.Serializer):
    pending_outbox_count = serializers.IntegerField()
    last_outbox_delivery_at = serializers.DateTimeField(allow_null=True)
    stale_assignment_count = serializers.IntegerField()
    orphaned_run_count = serializers.IntegerField()
    last_reconciliation_at = serializers.DateTimeField(allow_null=True)


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
