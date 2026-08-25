# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.agent_infra.models import ProjectAgentEnablement


class AgentEnablementService:
    @staticmethod
    def get_enabled_agents(workspace_id, project_id):
        return ProjectAgentEnablement.objects.filter(
            workspace_id=workspace_id, project_id=project_id, enabled=True
        )

    @staticmethod
    def check_assignment_allowed(workspace_id, project_id, agent_ref, assignment_type):
        try:
            enablement = ProjectAgentEnablement.objects.get(
                workspace_id=workspace_id,
                project_id=project_id,
                agent_ref=agent_ref,
                enabled=True,
            )
        except ProjectAgentEnablement.DoesNotExist:
            return False, "Agent not enabled for this project"
        if enablement.allowed_assignment_types and assignment_type not in enablement.allowed_assignment_types:
            return False, f"Assignment type '{assignment_type}' not allowed for agent '{agent_ref}'"
        return True, None
