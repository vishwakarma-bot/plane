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
    ReviewDisposition,
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
        run = attrs.get("run") or getattr(self.instance, "run", None)
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
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class AgentCatalogSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False, allow_null=True)
    catalog_path = serializers.CharField(required=False, allow_null=True)
    last_refreshed = serializers.CharField(required=False, allow_null=True)
    agents = serializers.ListField(child=serializers.DictField(), required=False)
    skills = serializers.ListField(child=serializers.DictField(), required=False)


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
