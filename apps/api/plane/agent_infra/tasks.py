# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from celery import shared_task

# Module imports
from plane.agent_infra.services.knowledge_authority import get_knowledge_authority_service
from plane.agent_infra.services.reconciliation import get_reconciliation_service
from plane.utils.exception_logger import log_exception


@shared_task
def process_agent_infra_outbox():
    """Periodic task to process outbox events."""
    try:
        return get_reconciliation_service().process_outbox()
    except Exception as exc:
        log_exception(exc)
        raise


@shared_task
def reconcile_agent_infra():
    """Periodic task to check for stale/orphaned entities."""
    try:
        return get_reconciliation_service().reconcile()
    except Exception as exc:
        log_exception(exc)
        raise


@shared_task
def cleanup_agent_infra_idempotency():
    """Periodic task to clean expired idempotency records."""
    try:
        deleted_count = get_reconciliation_service().cleanup_expired_idempotency()
        return {"deleted_count": deleted_count}
    except Exception as exc:
        log_exception(exc)
        raise


@shared_task
def check_knowledge_health():
    """Periodic task to detect stale sources and authority conflicts."""
    from plane.db.models import Project

    service = get_knowledge_authority_service()
    summary = {
        "projects_checked": 0,
        "stale_count": 0,
        "conflict_count": 0,
        "quarantine_count": 0,
    }

    try:
        for project in Project.objects.filter(is_agent_infra_enabled=True):
            result = service.check_project_knowledge_health(project.workspace_id, project.id)
            summary["projects_checked"] += 1
            summary["stale_count"] += result["stale_count"]
            summary["conflict_count"] += result["conflict_count"]
            summary["quarantine_count"] += result["quarantine_count"]
        return summary
    except Exception as exc:
        log_exception(exc)
        raise
