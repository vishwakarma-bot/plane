# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.db import transaction

from plane.agent_infra.models import AgentAssignment, AssignmentStatus

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    AssignmentStatus.PENDING: {AssignmentStatus.RUNNING, AssignmentStatus.CANCELLED},
    AssignmentStatus.RUNNING: {
        AssignmentStatus.COMPLETED,
        AssignmentStatus.FAILED,
        AssignmentStatus.CANCELLED,
    },
    AssignmentStatus.COMPLETED: set(),
    AssignmentStatus.FAILED: {AssignmentStatus.PENDING},
    AssignmentStatus.CANCELLED: set(),
}


def validate_status_transition(current: str, new: str) -> None:
    """Raise ValidationError if the status transition is not allowed."""
    if current == new:
        return

    allowed = VALID_STATUS_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValidationError(
            {
                "status": (
                    f"Invalid status transition from '{current}' to '{new}'. "
                    f"Allowed: {sorted(allowed) if allowed else '(terminal)'}"
                )
            }
        )


def get_pending_assignments(workspace_id, project_id):
    """Return pending assignments for the given workspace and project."""
    return (
        AgentAssignment.objects.filter(
            workspace_id=workspace_id,
            project_id=project_id,
            status=AssignmentStatus.PENDING,
        )
        .select_related("workspace", "project", "work_item")
        .order_by("created_at")
    )


def claim_assignment(assignment_id, service_id):
    """
    Atomically transition an assignment from pending to running.

    Returns the updated assignment on success.
    Raises ValidationError if the assignment is not pending or not found.
    """
    _ = service_id  # reserved for future audit attribution
    with transaction.atomic():
        assignment = (
            AgentAssignment.objects.select_for_update()
            .filter(pk=assignment_id, status=AssignmentStatus.PENDING)
            .first()
        )
        if assignment is None:
            existing = AgentAssignment.objects.filter(pk=assignment_id).first()
            if existing is None:
                raise ValidationError({"assignment": "Assignment not found."})
            raise ValidationError(
                {
                    "status": (
                        f"Cannot claim assignment in status '{existing.status}'. "
                        "Only pending assignments can be claimed."
                    )
                }
            )

        validate_status_transition(assignment.status, AssignmentStatus.RUNNING)
        assignment.status = AssignmentStatus.RUNNING
        assignment.save(update_fields=["status", "updated_at"])

    return assignment
