# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework.exceptions import NotFound

# Module imports
from plane.db.models import Project


class AgentInfraFeatureFlagMixin:
    """Ensure agent infrastructure endpoints are only accessible when enabled for the project."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        project = Project.objects.filter(
            workspace__slug=kwargs.get("slug"),
            pk=kwargs.get("project_id"),
        ).first()
        if not project or not project.is_agent_infra_enabled:
            raise NotFound("Agent infrastructure is not enabled for this project.")
