# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from celery import shared_task
from django.db import models

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
    """Periodic task to detect stale sources, authority conflicts, and index issues."""
    from datetime import timedelta

    from django.utils import timezone

    from plane.agent_infra.models import (
        AgentInfraAttentionItem,
        IndexRequestStatus,
        KnowledgeIndexRecord,
    )
    from plane.db.models import Project

    service = get_knowledge_authority_service()
    summary = {
        "projects_checked": 0,
        "stale_count": 0,
        "conflict_count": 0,
        "quarantine_count": 0,
        "index_stale_count": 0,
        "index_failed_count": 0,
    }

    try:
        now = timezone.now()
        stale_threshold = now - timedelta(hours=1)

        for project in Project.objects.filter(is_agent_infra_enabled=True):
            result = service.check_project_knowledge_health(project.workspace_id, project.id)
            summary["projects_checked"] += 1
            summary["stale_count"] += result["stale_count"]
            summary["conflict_count"] += result["conflict_count"]
            summary["quarantine_count"] += result["quarantine_count"]

            pending_records = KnowledgeIndexRecord.objects.filter(
                workspace_id=project.workspace_id,
                project_id=project.id,
                status__in=[IndexRequestStatus.PENDING, IndexRequestStatus.ACKNOWLEDGED],
                requested_at__lt=stale_threshold,
            )
            for record in pending_records:
                summary["index_stale_count"] += 1
                AgentInfraAttentionItem.objects.get_or_create(
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    entity_type="KnowledgeIndexRecord",
                    entity_id=record.id,
                    drift_type="index_stale",
                    resolved_at=None,
                    defaults={
                        "details": {
                            "record_id": str(record.id),
                            "action": record.action,
                            "status": record.status,
                            "requested_at": record.requested_at.isoformat(),
                        }
                    },
                )

            failed_records = KnowledgeIndexRecord.objects.filter(
                workspace_id=project.workspace_id,
                project_id=project.id,
                status=IndexRequestStatus.FAILED,
            ).exclude(retry_count__gte=models.F("max_retries"))
            for record in failed_records:
                summary["index_failed_count"] += 1
                AgentInfraAttentionItem.objects.get_or_create(
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    entity_type="KnowledgeIndexRecord",
                    entity_id=record.id,
                    drift_type="index_failed",
                    resolved_at=None,
                    defaults={
                        "details": {
                            "record_id": str(record.id),
                            "action": record.action,
                            "failure_reason": record.failure_reason,
                            "retry_count": record.retry_count,
                        }
                    },
                )

        return summary
    except Exception as exc:
        log_exception(exc)
        raise
