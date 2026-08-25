# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
import os
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Max, Q
from django.utils import timezone

from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraAttentionItem,
    AgentInfraOutbox,
    AgentRun,
    AssignmentStatus,
    AuthorizingReview,
    IdempotencyRecord,
    OutboxStatus,
    RunOutcome,
)
from plane.utils.exception_logger import log_exception
from plane.utils.url_security import pinned_fetch

logger = logging.getLogger("plane.worker")

_reconciliation_service = None


def get_last_reconciliation_cache_key(workspace_id, project_id) -> str:
    return f"agent_infra:last_reconciliation:{workspace_id}:{project_id}"


def get_reconciliation_service() -> "ReconciliationService":
    global _reconciliation_service
    if _reconciliation_service is None:
        _reconciliation_service = ReconciliationService()
    return _reconciliation_service


class ReconciliationService:
    STALE_THRESHOLD_MINUTES = 30
    ORPHANED_RUN_THRESHOLD_MINUTES = 30
    OUTBOX_BACKOFF_BASE_SECONDS = 60
    OUTBOX_BATCH_SIZE = 100
    IDEMPOTENCY_RETENTION_HOURS = 24

    def check_stale_assignments(self, workspace_id, project_id):
        """Find assignments stuck in 'running' for too long."""
        threshold = timezone.now() - timedelta(minutes=self.STALE_THRESHOLD_MINUTES)
        stale_assignments = AgentAssignment.objects.filter(
            workspace_id=workspace_id,
            project_id=project_id,
            status=AssignmentStatus.RUNNING,
            updated_at__lt=threshold,
        )

        attention_items = []
        for assignment in stale_assignments:
            attention_items.append(
                self.create_drift_attention_item(
                    entity=assignment,
                    drift_type="stale_assignment",
                    details={
                        "assignment_id": str(assignment.id),
                        "status": assignment.status,
                        "updated_at": assignment.updated_at.isoformat(),
                        "threshold_minutes": self.STALE_THRESHOLD_MINUTES,
                    },
                )
            )

        return list(stale_assignments), attention_items

    def check_orphaned_runs(self, workspace_id, project_id):
        """Find runs without an authorizing review past the expected window."""
        threshold = timezone.now() - timedelta(minutes=self.ORPHANED_RUN_THRESHOLD_MINUTES)
        orphaned_runs = (
            AgentRun.objects.filter(
                workspace_id=workspace_id,
                project_id=project_id,
                completed_at__isnull=False,
                completed_at__lt=threshold,
            )
            .filter(authorizing_review__isnull=True)
            .select_related("assignment")
        )

        attention_items = []
        for run in orphaned_runs:
            attention_items.append(
                self.create_drift_attention_item(
                    entity=run,
                    drift_type="orphaned_run",
                    details={
                        "run_id": str(run.id),
                        "assignment_id": str(run.assignment_id),
                        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                        "threshold_minutes": self.ORPHANED_RUN_THRESHOLD_MINUTES,
                    },
                )
            )

        return list(orphaned_runs), attention_items

    def reconcile_assignment_status(self, assignment_id):
        """Check if assignment status matches its runs' outcomes."""
        assignment = AgentAssignment.objects.select_related("workspace", "project").get(pk=assignment_id)
        runs = list(assignment.runs.order_by("-completed_at", "-created_at"))

        if not runs:
            if assignment.status == AssignmentStatus.RUNNING:
                drift_type = "running_without_runs"
                expected_status = AssignmentStatus.PENDING
            else:
                return {"assignment_id": str(assignment.id), "drift_detected": False}
        else:
            latest_run = runs[0]
            expected_status = self._expected_assignment_status(latest_run.outcome)
            drift_type = "status_mismatch"
            if expected_status is None or assignment.status == expected_status:
                return {
                    "assignment_id": str(assignment.id),
                    "drift_detected": False,
                    "current_status": assignment.status,
                    "expected_status": expected_status,
                }

        attention_item = self.create_drift_attention_item(
            entity=assignment,
            drift_type=drift_type,
            details={
                "assignment_id": str(assignment.id),
                "current_status": assignment.status,
                "expected_status": expected_status,
                "latest_run_id": str(runs[0].id) if runs else None,
                "latest_run_outcome": runs[0].outcome if runs else None,
            },
        )
        return {
            "assignment_id": str(assignment.id),
            "drift_detected": True,
            "current_status": assignment.status,
            "expected_status": expected_status,
            "attention_item_id": str(attention_item.id),
        }

    def create_drift_attention_item(self, entity, drift_type, details):
        """Create an attention item when drift is detected."""
        workspace_id = getattr(entity, "workspace_id", None)
        project_id = getattr(entity, "project_id", None)

        if workspace_id is None or project_id is None:
            assignment = getattr(entity, "assignment", None)
            if assignment is not None:
                workspace_id = assignment.workspace_id
                project_id = assignment.project_id

        attention_item, _created = AgentInfraAttentionItem.objects.get_or_create(
            workspace_id=workspace_id,
            project_id=project_id,
            entity_type=entity.__class__.__name__,
            entity_id=entity.id,
            drift_type=drift_type,
            resolved_at=None,
            defaults={"details": details},
        )
        if not _created and attention_item.details != details:
            attention_item.details = details
            attention_item.save(update_fields=["details", "updated_at"])

        logger.info(
            "Agent infra drift detected",
            extra={
                "drift_type": drift_type,
                "entity_type": attention_item.entity_type,
                "entity_id": str(attention_item.entity_id),
            },
        )
        return attention_item

    def process_outbox(self):
        """Process pending outbox events with retry logic."""
        now = timezone.now()
        pending_events = (
            AgentInfraOutbox.objects.filter(status=OutboxStatus.PENDING)
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
            .order_by("next_attempt_at", "created_at")[: self.OUTBOX_BATCH_SIZE]
        )

        processed = {"sent": 0, "failed": 0, "retried": 0}

        for event in pending_events:
            event.attempts += 1
            event.last_attempted_at = now

            try:
                self._deliver_outbox_event(event)
            except Exception as exc:
                log_exception(exc)
                event.error_message = str(exc)
                if event.attempts >= event.max_attempts:
                    event.status = OutboxStatus.FAILED
                    processed["failed"] += 1
                else:
                    event.next_attempt_at = now + timedelta(
                        seconds=self.OUTBOX_BACKOFF_BASE_SECONDS * (2 ** (event.attempts - 1))
                    )
                    processed["retried"] += 1
            else:
                event.status = OutboxStatus.SENT
                event.error_message = ""
                event.next_attempt_at = None
                processed["sent"] += 1

            event.save(
                update_fields=[
                    "attempts",
                    "last_attempted_at",
                    "next_attempt_at",
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )

        return processed

    def cleanup_expired_idempotency(self):
        """Remove expired idempotency records."""
        expired_before = timezone.now()
        result = IdempotencyRecord.objects.filter(expires_at__lt=expired_before).delete()
        if isinstance(result, tuple):
            return result[0]
        return result

    def reconcile(self, workspace_id=None, project_id=None):
        """Run stale/orphaned checks for one project or all agent-infra projects."""
        from plane.db.models import Project

        projects = Project.objects.filter(is_agent_infra_enabled=True)
        if workspace_id is not None:
            projects = projects.filter(workspace_id=workspace_id)
        if project_id is not None:
            projects = projects.filter(pk=project_id)

        summary = {
            "stale_assignments": 0,
            "orphaned_runs": 0,
            "status_drifts": 0,
        }

        for project in projects:
            stale_assignments, _ = self.check_stale_assignments(project.workspace_id, project.id)
            orphaned_runs, _ = self.check_orphaned_runs(project.workspace_id, project.id)
            summary["stale_assignments"] += len(stale_assignments)
            summary["orphaned_runs"] += len(orphaned_runs)

            running_assignments = AgentAssignment.objects.filter(
                workspace_id=project.workspace_id,
                project_id=project.id,
                status__in=[AssignmentStatus.RUNNING, AssignmentStatus.COMPLETED, AssignmentStatus.FAILED],
            )
            for assignment in running_assignments:
                result = self.reconcile_assignment_status(assignment.id)
                if result.get("drift_detected"):
                    summary["status_drifts"] += 1

            cache.set(
                get_last_reconciliation_cache_key(project.workspace_id, project.id),
                timezone.now(),
                timeout=None,
            )

        return summary

    def get_sync_status(self, workspace_id, project_id):
        """Return lightweight sync/reconciliation status for a project."""
        pending_outbox_count = AgentInfraOutbox.objects.filter(
            workspace_id=workspace_id,
            project_id=project_id,
            status=OutboxStatus.PENDING,
        ).count()

        last_outbox_delivery_at = (
            AgentInfraOutbox.objects.filter(
                workspace_id=workspace_id,
                project_id=project_id,
                status=OutboxStatus.SENT,
            ).aggregate(last_delivery=Max("last_attempted_at"))["last_delivery"]
        )

        unresolved_items = AgentInfraAttentionItem.objects.filter(
            workspace_id=workspace_id,
            project_id=project_id,
            resolved_at__isnull=True,
        )
        stale_assignment_count = unresolved_items.filter(drift_type="stale_assignment").count()
        orphaned_run_count = unresolved_items.filter(drift_type="orphaned_run").count()
        last_reconciliation_at = cache.get(
            get_last_reconciliation_cache_key(workspace_id, project_id)
        )

        return {
            "pending_outbox_count": pending_outbox_count,
            "last_outbox_delivery_at": last_outbox_delivery_at,
            "stale_assignment_count": stale_assignment_count,
            "orphaned_run_count": orphaned_run_count,
            "last_reconciliation_at": last_reconciliation_at,
        }

    def _expected_assignment_status(self, run_outcome):
        if run_outcome == RunOutcome.SUCCESS:
            return AssignmentStatus.COMPLETED
        if run_outcome in {RunOutcome.FAILURE, RunOutcome.BLOCKED}:
            return AssignmentStatus.FAILED
        if run_outcome == RunOutcome.PARTIAL:
            return AssignmentStatus.RUNNING
        return None

    def _resolve_callback_url(self, event_type: str) -> str:
        """Route agent_* events to A2A endpoint; others to the main event URL."""
        if event_type.startswith("agent_"):
            a2a_url = os.environ.get("DEVELOPMENT_CENTER_A2A_URL") or getattr(
                settings, "DEVELOPMENT_CENTER_A2A_URL", None
            )
            if a2a_url:
                return a2a_url
            base_url = os.environ.get("DEVELOPMENT_CENTER_EVENT_URL") or getattr(
                settings, "DEVELOPMENT_CENTER_EVENT_URL", None
            )
            if base_url:
                return base_url.rstrip("/") + "/a2a"
            raise RuntimeError(
                "DEVELOPMENT_CENTER_A2A_URL or DEVELOPMENT_CENTER_EVENT_URL is not configured"
            )

        callback_url = os.environ.get("DEVELOPMENT_CENTER_EVENT_URL") or getattr(
            settings, "DEVELOPMENT_CENTER_EVENT_URL", None
        )
        if not callback_url:
            raise RuntimeError("DEVELOPMENT_CENTER_EVENT_URL is not configured")
        return callback_url

    def _deliver_outbox_event(self, event: AgentInfraOutbox) -> None:
        callback_url = self._resolve_callback_url(event.event_type)

        body = {
            "event_type": event.event_type,
            "idempotency_key": str(event.idempotency_key),
            "workspace_id": str(event.workspace_id),
            "project_id": str(event.project_id),
            "payload": event.payload,
        }
        response = pinned_fetch(
            "POST",
            callback_url,
            headers={
                "Content-Type": "application/json",
                "X-Idempotency-Key": str(event.idempotency_key),
            },
            data=json.dumps(body),
            timeout=30,
        )

        if response.status_code >= 400:
            raise requests.HTTPError(
                f"Development Center callback failed with status {response.status_code}: {response.text}",
                response=response,
            )
