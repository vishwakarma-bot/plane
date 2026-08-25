# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from plane.agent_infra.models import ModelRoutingConfig
from plane.agent_infra.models.model_routing_config import BudgetPeriod

PERIOD_DURATIONS = {
    BudgetPeriod.DAILY: timedelta(days=1),
    BudgetPeriod.WEEKLY: timedelta(weeks=1),
    BudgetPeriod.MONTHLY: timedelta(days=30),
}


class ModelRoutingService:
    @staticmethod
    def _period_expired(config):
        """Check if the budget period has elapsed without mutating state."""
        if config.budget_limit_usd is None:
            return False
        duration = PERIOD_DURATIONS.get(config.budget_period)
        if duration is None:
            return False
        if config.budget_period_started_at is None:
            return True
        return timezone.now() >= config.budget_period_started_at + duration

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
        used = Decimal(0) if ModelRoutingService._period_expired(config) else config.budget_used_usd
        remaining = config.budget_limit_usd - used
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
        """Atomically check and reserve budget with period reset under row lock."""
        with transaction.atomic():
            try:
                config = ModelRoutingConfig.objects.select_for_update().get(
                    workspace_id=workspace_id, project_id=project_id, model_ref=model_ref
                )
            except ModelRoutingConfig.DoesNotExist:
                return True, "No routing config"

            if config.budget_limit_usd is None:
                config.budget_used_usd = F("budget_used_usd") + cost_usd
                config.save(update_fields=["budget_used_usd", "updated_at"])
                return True, "No budget limit"

            if ModelRoutingService._period_expired(config):
                config.budget_used_usd = Decimal(0)
                config.budget_period_started_at = timezone.now()

            if config.budget_used_usd + cost_usd > config.budget_limit_usd:
                remaining = config.budget_limit_usd - config.budget_used_usd
                return False, f"Budget exceeded: ${remaining:.2f} remaining, ${cost_usd:.2f} requested"

            config.budget_used_usd += cost_usd
            config.save(update_fields=["budget_used_usd", "budget_period_started_at", "updated_at"])
            return True, None
