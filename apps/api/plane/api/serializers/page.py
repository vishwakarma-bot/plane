# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.api.serializers.base import BaseSerializer
from plane.db.models import Page
from plane.utils.content_validator import validate_html_content


class PageSerializer(BaseSerializer):
    """Public API representation of a project page."""

    class Meta:
        model = Page
        fields = [
            "id",
            "name",
            "description_html",
            "description_json",
            "access",
            "color",
            "parent",
            "is_locked",
            "archived_at",
            "view_props",
            "logo_props",
            "workspace",
            "owned_by",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "owned_by",
            "archived_at",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate_description_html(self, value):
        if not value:
            return value

        is_valid, error_message, sanitized_html = validate_html_content(value)
        if not is_valid:
            raise serializers.ValidationError(error_message)
        return sanitized_html if sanitized_html is not None else value


class PageArchiveSerializer(serializers.Serializer):
    archived = serializers.BooleanField(required=True)
