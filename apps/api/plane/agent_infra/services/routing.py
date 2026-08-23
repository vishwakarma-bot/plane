# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import F

from plane.agent_infra.models import ModelRoutingConfig


class ModelRoutingService:
    @staticmethod
    def get_routing_config(workspace_id, project_id):
        return ModelRoutingConfig.objects.filter(
            workspace_id=workspace_id, project_id=project_id, enabled=True
        ).order_by("routing_priority")

    @staticmethod
    def check_budget(workspace_id, project_id, model_ref, estimated_cost):
        """Read-only budget check for display/estimation. Does not reserve budget."""
        try:
            config = ModelRoutingConfig.objects.get(
                workspace_id=workspace_id, project_id=project_id, model_ref=model_ref
            )
        except ModelRoutingConfig.DoesNotExist:
            return True, "No routing config"
        if config.budget_limit_usd is None:
            return True, "No budget limit"
        remaining = config.budget_limit_usd - config.budget_used_usd
        if estimated_cost > remaining:
            return False, f"Budget exceeded: ${remaining} remaining, ${estimated_cost} requested"
        return True, None

    @staticmethod
    def record_usage(workspace_id, project_id, model_ref, cost_usd):
        """Record usage after the fact. Use reserve_budget() for enforcement."""
        ModelRoutingConfig.objects.filter(
            workspace_id=workspace_id, project_id=project_id, model_ref=model_ref
        ).update(budget_used_usd=F("budget_used_usd") + cost_usd)

    @staticmethod
    def reserve_budget(workspace_id, project_id, model_ref, cost_usd):
        """Atomically check and reserve budget in a single UPDATE."""
        try:
            config = ModelRoutingConfig.objects.get(
                workspace_id=workspace_id, project_id=project_id, model_ref=model_ref
            )
        except ModelRoutingConfig.DoesNotExist:
            return True, "No routing config"
        if config.budget_limit_usd is None:
            ModelRoutingConfig.objects.filter(pk=config.pk).update(
                budget_used_usd=F("budget_used_usd") + cost_usd
            )
            return True, "No budget limit"
        updated = ModelRoutingConfig.objects.filter(
            pk=config.pk,
            budget_limit_usd__gte=F("budget_used_usd") + cost_usd,
        ).update(budget_used_usd=F("budget_used_usd") + cost_usd)
        if updated:
            return True, None
        config.refresh_from_db()
        remaining = config.budget_limit_usd - config.budget_used_usd
        return False, f"Budget exceeded: ${remaining:.2f} remaining, ${cost_usd:.2f} requested"
