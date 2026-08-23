# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.agent_infra.models import (
    AgentAssignment,
    AgentRun,
    ArtifactReference,
    AuthorizingReview,
    ReviewDisposition,
)
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
