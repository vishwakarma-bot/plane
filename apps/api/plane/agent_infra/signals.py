# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraOutbox,
    AssignmentStatus,
    OutboxEventType,
    ReviewDisposition,
)


def _create_outbox_event(*, workspace_id, project_id, event_type, payload):
    AgentInfraOutbox.objects.create(
        workspace_id=workspace_id,
        project_id=project_id,
        event_type=event_type,
        payload=payload,
    )


def _assignment_payload(assignment):
    return {
        "assignment_id": str(assignment.id),
        "work_item_id": str(assignment.work_item_id),
        "agent_ref": assignment.agent_ref,
        "assignment_type": assignment.assignment_type,
        "status": assignment.status,
    }


@receiver(pre_save, sender=AgentAssignment)
def capture_assignment_previous_status(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_status = (
            AgentAssignment.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        )
    else:
        instance._previous_status = None


@receiver(post_save, sender=AgentAssignment)
def assignment_outbox_events(sender, instance, created, **kwargs):
    if created:
        _create_outbox_event(
            workspace_id=instance.workspace_id,
            project_id=instance.project_id,
            event_type=OutboxEventType.ASSIGNMENT_CREATED,
            payload=_assignment_payload(instance),
        )
        return

    previous_status = getattr(instance, "_previous_status", None)
    if (
        previous_status != AssignmentStatus.CANCELLED
        and instance.status == AssignmentStatus.CANCELLED
    ):
        _create_outbox_event(
            workspace_id=instance.workspace_id,
            project_id=instance.project_id,
            event_type=OutboxEventType.ASSIGNMENT_CANCELLED,
            payload=_assignment_payload(instance),
        )


@receiver(post_save, sender=ReviewDisposition)
def disposition_created_outbox(sender, instance, created, **kwargs):
    if not created:
        return

    run = instance.run
    _create_outbox_event(
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        event_type=OutboxEventType.DISPOSITION_CREATED,
        payload={
            "disposition_id": str(instance.id),
            "run_id": str(run.id),
            "assignment_id": str(run.assignment_id),
            "reviewer_id": str(instance.reviewer_id),
            "disposition": instance.disposition,
            "reason": instance.reason,
        },
    )
