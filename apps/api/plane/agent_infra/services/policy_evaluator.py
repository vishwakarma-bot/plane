# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Deterministic policy evaluator for the authorization system.

Evaluation algorithm:
1. Check active emergency denies first (always override)
2. Load all active policies for the workspace+project scope
3. Filter to policies matching the request (subject, resource, action, conditions)
4. Sort by priority (lower number = higher precedence)
5. Apply deny-wins semantics: first matching deny blocks immediately
6. If no deny, first matching allow or require_approval wins
7. Default outcome is deny (fail-closed)
8. Check separation-of-duty constraints
9. Record the decision with full evidence trail

The evaluator is pure computation — no AI, no LLM, no non-determinism.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class EvaluationRequest:
    """Input to the policy evaluator."""

    workspace_id: UUID
    project_id: UUID | None
    subject_type: str
    subject_ref: str
    resource_type: str
    resource_ref: str
    action: str
    context: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    run_id: UUID | None = None
    actor: Any | None = None


@dataclass
class PolicyMatch:
    """A policy that matched during evaluation, with match reason."""

    policy_id: UUID
    policy_name: str
    priority: int
    effect: str
    match_reason: str


@dataclass
class EvaluationResult:
    """Output of the policy evaluator — deterministic, fully evidenced."""

    outcome: str  # "allow", "deny", "require_approval"
    deciding_policy_id: UUID | None
    deciding_policy_name: str | None
    reason: str
    matching_policies: list[PolicyMatch]
    separation_of_duty_violations: list[str]
    emergency_deny_active: bool = False
    emergency_deny_id: UUID | None = None


class PolicyEvaluator:
    """Deterministic policy engine. No AI in the decision path."""

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Evaluate a request against all applicable policies.

        Returns a fully-evidenced result. Does NOT persist — call
        record_decision() separately to create the audit record.

        Runs inside a transaction to support select_for_update() in SoD checks.
        """
        with transaction.atomic():
            return self._evaluate_inner(request)

    def _evaluate_inner(self, request: EvaluationRequest) -> EvaluationResult:
        """Core evaluation logic, must run inside a transaction."""
        from plane.agent_infra.models import (
            AuthorizationPolicy,
            EmergencyDeny,
            PolicyStatus,
            SeparationOfDutyConstraint,
        )

        # Step 1: Check emergency denies
        from django.db.models import Q

        emergencies = EmergencyDeny.objects.filter(
            workspace_id=request.workspace_id,
            is_active=True,
        ).filter(
            Q(project_id__isnull=True) | Q(project_id=request.project_id)
        )

        for emergency in emergencies:
            if self._emergency_matches(emergency, request):
                return EvaluationResult(
                    outcome="deny",
                    deciding_policy_id=emergency.policy_id,
                    deciding_policy_name=f"emergency-deny-{emergency.id}",
                    reason=f"Emergency deny active: {emergency.reason}",
                    matching_policies=[],
                    separation_of_duty_violations=[],
                    emergency_deny_active=True,
                    emergency_deny_id=emergency.id,
                )

        # Step 2: Load applicable policies
        policies = self._load_applicable_policies(request)

        # Step 3: Filter to matching policies
        matches: list[PolicyMatch] = []
        for policy in policies:
            match_reason = self._policy_matches(policy, request)
            if match_reason:
                matches.append(PolicyMatch(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    priority=policy.priority,
                    effect=policy.effect,
                    match_reason=match_reason,
                ))

        # Step 4: Sort by priority (already sorted from DB, but ensure)
        matches.sort(key=lambda m: m.priority)

        # Step 5: Deny-wins semantics
        deciding = None
        outcome = "deny"  # fail-closed default
        reason = "No matching policy found — default deny (fail-closed)"

        for match in matches:
            if match.effect == "deny":
                deciding = match
                outcome = "deny"
                reason = f"Policy '{match.policy_name}' (priority {match.priority}) denies this action: {match.match_reason}"
                break

        if deciding is None:
            for match in matches:
                if match.effect in ("allow", "require_approval"):
                    deciding = match
                    outcome = match.effect
                    reason = (
                        f"Policy '{match.policy_name}' (priority {match.priority}) "
                        f"{'allows' if match.effect == 'allow' else 'requires approval for'} "
                        f"this action: {match.match_reason}"
                    )
                    break

        # Step 6: Check separation-of-duty constraints
        sod_violations = self._check_separation_of_duty(request)

        if sod_violations and outcome in ("allow", "require_approval"):
            outcome = "deny"
            reason = f"Separation-of-duty violation: {'; '.join(sod_violations)}"

        return EvaluationResult(
            outcome=outcome,
            deciding_policy_id=deciding.policy_id if deciding else None,
            deciding_policy_name=deciding.policy_name if deciding else None,
            reason=reason,
            matching_policies=matches,
            separation_of_duty_violations=sod_violations,
        )

    def simulate(self, request: EvaluationRequest) -> EvaluationResult:
        """Simulate policy evaluation without recording.

        evaluate() already runs inside a transaction, so this is a
        direct delegation. Kept as a semantic entry point.
        """
        return self.evaluate(request)

    def record_decision(
        self,
        request: EvaluationRequest,
        result: EvaluationResult,
    ) -> Any:
        """Persist an evaluation result as an immutable PolicyDecision record."""
        from plane.agent_infra.models import ActionApproval, ApprovalStatus, PolicyDecision

        decision = PolicyDecision.objects.create(
            workspace_id=request.workspace_id,
            project_id=request.project_id,
            subject_type=request.subject_type,
            subject_ref=request.subject_ref,
            resource_type=request.resource_type,
            resource_ref=request.resource_ref,
            action=request.action,
            outcome=result.outcome,
            matching_policies=[
                {
                    "policy_id": str(m.policy_id),
                    "policy_name": m.policy_name,
                    "priority": m.priority,
                    "effect": m.effect,
                    "match_reason": m.match_reason,
                }
                for m in result.matching_policies
            ],
            deciding_policy_id=result.deciding_policy_id,
            evaluation_context=request.context,
            reason=result.reason,
            correlation_id=request.correlation_id,
            run_id=request.run_id,
        )

        if decision.outcome == "require_approval":
            target_digest = ""
            if request.context:
                import hashlib as _hashlib
                import json as _json
                digest_input = _json.dumps(
                    {"resource_type": request.resource_type, "resource_ref": request.resource_ref,
                     "action": request.action, "context": request.context},
                    sort_keys=True, default=str,
                )
                target_digest = _hashlib.sha256(digest_input.encode()).hexdigest()[:32]

            ActionApproval.objects.create(
                workspace_id=decision.workspace_id,
                project_id=decision.project_id,
                policy_decision=decision,
                subject_type=request.subject_type,
                subject_ref=request.subject_ref,
                action=request.action,
                target_type=request.resource_type,
                target_ref=request.resource_ref,
                target_digest=target_digest,
                risk_level=request.context.get("risk_level", "medium") if request.context else "medium",
                status=ApprovalStatus.PENDING,
                requested_by=getattr(request, "actor", None),
                expires_at=timezone.now() + timedelta(hours=24),
            )

        return decision

    def evaluate_and_record(self, request: EvaluationRequest) -> tuple[EvaluationResult, Any]:
        """Evaluate and persist the decision atomically.

        Uses a single outer transaction; evaluate()'s nested atomic()
        becomes a savepoint so the SoD lock is held through recording.
        """
        with transaction.atomic():
            result = self.evaluate(request)
            decision = self.record_decision(request, result)
            return result, decision

    def diff_policies(
        self,
        workspace_id: UUID,
        project_id: UUID | None,
        policy_a_id: UUID,
        policy_b_id: UUID,
    ) -> dict[str, Any]:
        """Compute semantic diff between two policy revisions."""
        from plane.agent_infra.models import AuthorizationPolicy
        from django.db.models import Q

        scope_filter = {"workspace_id": workspace_id}
        if project_id:
            scope_q = Q(project_id=project_id) | Q(project_id__isnull=True)
        else:
            scope_q = Q(project_id__isnull=True)

        policy_a = AuthorizationPolicy.objects.filter(**scope_filter).filter(scope_q).get(id=policy_a_id)
        policy_b = AuthorizationPolicy.objects.filter(**scope_filter).filter(scope_q).get(id=policy_b_id)

        diff = {
            "policy_name": policy_a.name,
            "revision_a": policy_a.revision_number,
            "revision_b": policy_b.revision_number,
            "changes": [],
        }

        compare_fields = [
            "priority", "effect", "subjects", "resources", "actions",
            "conditions", "separation_of_duty", "autonomy_classification",
            "emergency", "scope",
        ]

        for field_name in compare_fields:
            val_a = getattr(policy_a, field_name)
            val_b = getattr(policy_b, field_name)
            if val_a != val_b:
                diff["changes"].append({
                    "field": field_name,
                    "from": val_a,
                    "to": val_b,
                })

        return diff

    def blast_radius(
        self,
        workspace_id: UUID,
        project_id: UUID | None,
        policy_id: UUID,
    ) -> dict[str, Any]:
        """Estimate the blast radius of a policy change.

        Returns counts of subjects, resources, and recent decisions
        that would be affected if this policy is activated/modified.
        """
        from plane.agent_infra.models import (
            AuthorizationPolicy,
            PolicyDecision,
            ProjectAgentEnablement,
        )
        from django.db.models import Q

        scope_filter = {"workspace_id": workspace_id}
        if project_id:
            scope_q = Q(project_id=project_id) | Q(project_id__isnull=True)
        else:
            scope_q = Q(project_id__isnull=True)

        policy = AuthorizationPolicy.objects.filter(**scope_filter).filter(scope_q).get(id=policy_id)

        affected_agents = set()
        for subject in policy.subjects:
            if subject.get("ref") == "*":
                enablements = ProjectAgentEnablement.objects.filter(
                    workspace_id=workspace_id, enabled=True
                ).values_list("agent_ref", flat=True)
                affected_agents.update(enablements)
            else:
                affected_agents.add(subject.get("ref"))

        recent_decisions = PolicyDecision.objects.filter(
            workspace_id=workspace_id,
            action__in=[a.get("name", a) if isinstance(a, dict) else a for a in policy.actions],
        ).count()

        return {
            "policy_name": policy.name,
            "policy_effect": policy.effect,
            "affected_subjects": list(affected_agents),
            "affected_subject_count": len(affected_agents),
            "affected_resource_types": [r.get("type") for r in policy.resources],
            "affected_actions": [a.get("name", a) if isinstance(a, dict) else a for a in policy.actions],
            "recent_decisions_affected": recent_decisions,
            "scope": policy.scope,
            "priority": policy.priority,
        }

    def _emergency_matches(self, emergency, request: EvaluationRequest) -> bool:
        """Check if an emergency deny applies to this request."""
        if not emergency.scope_filter:
            return True

        scope = emergency.scope_filter
        if "subject_types" in scope:
            if request.subject_type not in scope["subject_types"]:
                return False
        if "resource_types" in scope:
            if request.resource_type not in scope["resource_types"]:
                return False
        if "actions" in scope:
            if request.action not in scope["actions"]:
                return False
        return True

    def _load_applicable_policies(self, request: EvaluationRequest):
        """Load all active policies for the workspace+project scope."""
        from plane.agent_infra.models import AuthorizationPolicy, PolicyStatus

        now = timezone.now()

        qs = AuthorizationPolicy.objects.filter(
            workspace_id=request.workspace_id,
            status=PolicyStatus.ACTIVE,
        ).filter(
            models_Q_expired_or_null(now),
        ).order_by("priority", "-revision_number")

        if request.project_id:
            from django.db.models import Q
            qs = qs.filter(
                Q(project_id=request.project_id) | Q(project_id__isnull=True)
            )
        else:
            qs = qs.filter(project_id__isnull=True)

        return qs

    def _policy_matches(self, policy, request: EvaluationRequest) -> str | None:
        """Check if a policy matches the request. Returns match reason or None.

        Defensively catches TypeError/AttributeError from malformed policy JSON
        and treats them as non-matching (fail-closed at the evaluation layer).
        """
        try:
            if not self._subjects_match(policy.subjects, request):
                return None
            if not self._resources_match(policy.resources, request):
                return None
            if not self._actions_match(policy.actions, request):
                return None
            if policy.conditions and not self._conditions_match(policy.conditions, request):
                return None
        except (TypeError, AttributeError, KeyError):
            return None

        if policy.autonomy_classification:
            ctx_autonomy = request.context.get("autonomy_classification")
            if not ctx_autonomy or ctx_autonomy != policy.autonomy_classification:
                return None

        return (
            f"subject={request.subject_type}:{request.subject_ref}, "
            f"resource={request.resource_type}:{request.resource_ref}, "
            f"action={request.action}"
        )

    def _subjects_match(self, subjects: list[dict], request: EvaluationRequest) -> bool:
        for subject in subjects:
            if subject.get("type") == request.subject_type:
                ref = subject.get("ref", "*")
                if ref == "*" or ref == request.subject_ref:
                    if self._subject_conditions_match(subject.get("conditions"), request):
                        return True
        return False

    def _subject_conditions_match(self, conditions: dict | None, request: EvaluationRequest) -> bool:
        if not conditions:
            return True
        for key, expected in conditions.items():
            actual = request.context.get(f"subject.{key}")
            if actual is None:
                actual = request.context.get(key)
            if actual != expected:
                return False
        return True

    def _resources_match(self, resources: list[dict], request: EvaluationRequest) -> bool:
        for resource in resources:
            if resource.get("type") == request.resource_type:
                ref = resource.get("ref", "*")
                if ref == "*" or ref == request.resource_ref:
                    if self._resource_conditions_match(resource.get("conditions"), request):
                        return True
        return False

    def _resource_conditions_match(self, conditions: dict | None, request: EvaluationRequest) -> bool:
        if not conditions:
            return True
        for key, expected in conditions.items():
            actual = request.context.get(f"resource.{key}", request.context.get(key))
            if actual != expected:
                return False
        return True

    def _actions_match(self, actions: list[dict], request: EvaluationRequest) -> bool:
        for action in actions:
            action_name = action.get("name") if isinstance(action, dict) else action
            if action_name == request.action or action_name == "*":
                return True
        return False

    def _conditions_match(self, conditions: list[dict], request: EvaluationRequest) -> bool:
        """All conditions must match (AND semantics)."""
        for condition in conditions:
            field_path = condition.get("field", "")
            operator = condition.get("operator", "eq")
            expected = condition.get("value")

            actual = self._resolve_field(field_path, request.context)

            if not self._compare(actual, operator, expected):
                return False
        return True

    def _resolve_field(self, field_path: str, context: dict) -> Any:
        """Resolve a dot-path field from the evaluation context."""
        parts = field_path.split(".")
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Deterministic comparison."""
        if operator == "eq":
            return actual == expected
        elif operator == "neq":
            return actual != expected
        elif operator == "in":
            return actual in (expected or [])
        elif operator == "not_in":
            return actual not in (expected or [])
        elif operator == "gt":
            return actual is not None and actual > expected
        elif operator == "gte":
            return actual is not None and actual >= expected
        elif operator == "lt":
            return actual is not None and actual < expected
        elif operator == "lte":
            return actual is not None and actual <= expected
        elif operator == "exists":
            return actual is not None
        elif operator == "not_exists":
            return actual is None
        return False

    def _check_separation_of_duty(self, request: EvaluationRequest) -> list[str]:
        """Check all active separation-of-duty constraints.

        Locks the constraint rows themselves to serialize concurrent evaluations
        that target the same conflicting actions. This ensures two concurrent
        evaluate_and_record() calls cannot both observe "no prior decision" and
        both return allow.
        """
        from plane.agent_infra.models import (
            ActionApproval,
            ApprovalStatus,
            PolicyDecision,
            SeparationOfDutyConstraint,
        )

        constraints = SeparationOfDutyConstraint.objects.select_for_update().filter(
            workspace_id=request.workspace_id,
            is_active=True,
        )

        if request.project_id:
            from django.db.models import Q
            constraints = constraints.filter(
                Q(project_id=request.project_id) | Q(project_id__isnull=True)
            )

        violations = []
        for constraint in constraints:
            if request.action not in constraint.conflicting_actions:
                continue

            other_actions = [
                a for a in constraint.conflicting_actions if a != request.action
            ]

            scope_filter = {"workspace_id": request.workspace_id}
            if constraint.scope == "run":
                if not request.run_id:
                    continue
                scope_filter["run_id"] = request.run_id
            elif constraint.scope == "assignment":
                if not request.correlation_id:
                    continue
                scope_filter["correlation_id"] = request.correlation_id
            elif constraint.scope == "project":
                if not request.project_id:
                    continue
                scope_filter["project_id"] = request.project_id

            allowed_directly = PolicyDecision.objects.filter(
                subject_type=request.subject_type,
                subject_ref=request.subject_ref,
                action__in=other_actions,
                outcome="allow",
                **scope_filter,
            ).exists()

            approved_via_workflow = PolicyDecision.objects.filter(
                subject_type=request.subject_type,
                subject_ref=request.subject_ref,
                action__in=other_actions,
                outcome="require_approval",
                approval_requests__status=ApprovalStatus.APPROVED,
                **scope_filter,
            ).exists()

            if allowed_directly or approved_via_workflow:
                violations.append(
                    f"Constraint '{constraint.name}': actor {request.subject_ref} "
                    f"already performed {other_actions} in this {constraint.scope}"
                )

        return violations


def models_Q_expired_or_null(now):
    """Build a Q object for policies not yet expired."""
    from django.db.models import Q
    return Q(expires_at__isnull=True) | Q(expires_at__gt=now)
