# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework.exceptions import NotFound

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.authentication.session import BaseSessionAuthentication
from plane.db.models import Project


class AgentInfraFeatureFlagMixin:
    """
    Ensure agent infrastructure endpoints are only accessible when enabled
    for the project, and support both session (browser) and API-key
    (machine) authentication on the same /api/v1/ route.
    """

    authentication_classes = [BaseSessionAuthentication, APIKeyAuthentication]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        project = Project.objects.filter(
            workspace__slug=kwargs.get("slug"),
            pk=kwargs.get("project_id"),
        ).first()
        if not project or not project.is_agent_infra_enabled:
            raise NotFound("Agent infrastructure is not enabled for this project.")
