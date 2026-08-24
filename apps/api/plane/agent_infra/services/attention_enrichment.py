# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.agent_infra.models import AgentAssignment, AgentRun, AuthorizingReview

RUN_ENTITY_TYPES = {"agent_run", "AgentRun"}
REVIEW_ENTITY_TYPES = {"authorizing_review", "AuthorizingReview"}
ASSIGNMENT_ENTITY_TYPES = {"agent_assignment", "AgentAssignment"}


def build_attention_enrichment_cache(items):
    if not items:
        return {}

    run_ids = set()
    review_ids = set()
    assignment_ids = set()

    for item in items:
        details = item.details or {}
        entity_type = item.entity_type
        entity_id = str(item.entity_id)

        if entity_type in RUN_ENTITY_TYPES:
            run_ids.add(entity_id)
        elif entity_type in REVIEW_ENTITY_TYPES:
            review_ids.add(entity_id)
        elif entity_type in ASSIGNMENT_ENTITY_TYPES:
            assignment_ids.add(entity_id)

        if details.get("run_id"):
            run_ids.add(str(details["run_id"]))
        if details.get("assignment_id"):
            assignment_ids.add(str(details["assignment_id"]))
        if details.get("latest_run_id"):
            run_ids.add(str(details["latest_run_id"]))

    runs_by_id = {
        str(run.id): run
        for run in AgentRun.objects.filter(id__in=run_ids).select_related(
            "assignment",
            "assignment__work_item",
            "assignment__work_item__project",
        )
    }

    reviews_by_id = {
        str(review.id): review
        for review in AuthorizingReview.objects.filter(id__in=review_ids).select_related(
            "run",
            "run__assignment",
            "run__assignment__work_item",
            "run__assignment__work_item__project",
        )
    }

    assignments_by_id = {
        str(assignment.id): assignment
        for assignment in AgentAssignment.objects.filter(id__in=assignment_ids).select_related(
            "work_item",
            "work_item__project",
        )
    }

    return {
        str(item.id): _merge_attention_details(
            item,
            runs_by_id=runs_by_id,
            reviews_by_id=reviews_by_id,
            assignments_by_id=assignments_by_id,
        )
        for item in items
    }


def enrich_attention_item_details(item):
    return build_attention_enrichment_cache([item]).get(str(item.id), dict(item.details or {}))


def _work_item_details(work_item):
    if work_item is None:
        return {}

    project = work_item.project
    identifier = (
        f"{project.identifier}-{work_item.sequence_id}"
        if project and project.identifier
        else str(work_item.sequence_id)
    )
    return {
        "work_item_id": str(work_item.id),
        "work_item_title": work_item.name,
        "work_item_identifier": identifier,
    }


def _apply_assignment_details(details, assignment):
    if assignment is None:
        return

    details.setdefault("agent_ref", assignment.agent_ref)
    details.setdefault("assignment_type", assignment.assignment_type)
    details.update(_work_item_details(assignment.work_item))


def _apply_run_details(details, run):
    if run is None:
        return

    details.setdefault("run_id", str(run.id))
    details.setdefault("agent_ref", run.agent_ref)
    if run.progression_outcome:
        details.setdefault("progression_outcome", run.progression_outcome)
    if run.progression_reason:
        details.setdefault("progression_reason", run.progression_reason)


def _merge_attention_details(item, *, runs_by_id, reviews_by_id, assignments_by_id):
    details = dict(item.details or {})
    entity_type = item.entity_type
    entity_id = str(item.entity_id)

    run = None
    assignment = None

    if entity_type in RUN_ENTITY_TYPES:
        run = runs_by_id.get(entity_id)
    elif entity_type in REVIEW_ENTITY_TYPES:
        review = reviews_by_id.get(entity_id)
        if review is not None:
            run = review.run
            details.setdefault("run_id", str(review.run_id))
            details.setdefault("verdict", review.verdict)
            details.setdefault("reason", review.reason)
            details.setdefault("reviewer_agent_ref", review.reviewer_agent_ref)
    elif entity_type in ASSIGNMENT_ENTITY_TYPES:
        assignment = assignments_by_id.get(entity_id)

    if run is None and details.get("run_id"):
        run = runs_by_id.get(str(details["run_id"]))
    if run is None and details.get("latest_run_id"):
        run = runs_by_id.get(str(details["latest_run_id"]))

    if assignment is None and details.get("assignment_id"):
        assignment = assignments_by_id.get(str(details["assignment_id"]))
    if assignment is None and run is not None and run.assignment_id:
        assignment = run.assignment

    _apply_run_details(details, run)
    _apply_assignment_details(details, assignment)

    return details
