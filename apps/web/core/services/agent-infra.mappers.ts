/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  TAgentActivityItem,
  TAgentAssignment,
  TAgentOverviewStats,
  TAgentRun,
  TAssignmentStatus,
  TAssignmentType,
  TAttentionQueueItem,
  TRunOutcome,
  TSyncStatus,
  TSyncStatusData,
} from "@/components/agent-infra/mock-data";
import type {
  TAgentAssignmentApi,
  TAgentAttentionItemApi,
  TAgentRunApi,
  TAgentSyncStatusApi,
} from "@/services/agent-infra.service";

const ASSIGNMENT_TYPE_MAP: Record<string, TAssignmentType> = {
  qa: "qa",
  development: "dev",
  dev: "dev",
  review: "review",
  research: "research",
};

const RUN_OUTCOME_MAP: Record<string, TRunOutcome> = {
  success: "success",
  failure: "failed",
  failed: "failed",
  partial: "partial",
  blocked: "failed",
};

const STALE_SYNC_THRESHOLD_MS = 5 * 60 * 1000;
const DISCONNECTED_SYNC_THRESHOLD_MS = 30 * 60 * 1000;

function formatAgentName(agentRef: string): string {
  const slug = agentRef.split("/").pop() ?? agentRef;
  return slug
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function capitalize(value: string): string {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function mapAssignmentType(value: string): TAssignmentType {
  return ASSIGNMENT_TYPE_MAP[value] ?? "dev";
}

function mapRunOutcome(value: string): TRunOutcome {
  return RUN_OUTCOME_MAP[value] ?? "partial";
}

function mapAssignmentStatus(value: string): TAssignmentStatus {
  if (
    value === "pending" ||
    value === "running" ||
    value === "completed" ||
    value === "failed" ||
    value === "cancelled"
  ) {
    return value;
  }
  return "pending";
}

export function mapAgentRun(apiRun: TAgentRunApi): TAgentRun {
  const tokenCount = (apiRun.tokens_in ?? 0) + (apiRun.tokens_out ?? 0);
  const durationMs =
    apiRun.completed_at && apiRun.started_at
      ? new Date(apiRun.completed_at).getTime() - new Date(apiRun.started_at).getTime()
      : 0;

  return {
    id: apiRun.id,
    attempt: 1,
    model: apiRun.model_used,
    outcome: mapRunOutcome(apiRun.outcome),
    durationMs: Math.max(durationMs, 0),
    tokenCount,
    costUsd: Number(apiRun.cost_usd ?? 0),
    startedAt: apiRun.started_at,
    completedAt: apiRun.completed_at ?? undefined,
    isActive: !apiRun.completed_at,
  };
}

function buildObservedState(assignment: TAgentAssignmentApi, runs: TAgentRunApi[]): string | undefined {
  const assignmentRuns = [...runs]
    .filter((run) => run.assignment === assignment.id)
    .sort(
      (left: TAgentRunApi, right: TAgentRunApi) =>
        new Date(right.started_at).getTime() - new Date(left.started_at).getTime()
    );

  const latestRun = assignmentRuns[0];
  if (latestRun) {
    if (!latestRun.completed_at) {
      return `Running on ${latestRun.model_used}`;
    }
    return `${capitalize(mapRunOutcome(latestRun.outcome))} on ${latestRun.model_used}`;
  }

  if (assignment.status !== "pending") {
    return capitalize(assignment.status);
  }

  return undefined;
}

export function mapAgentAssignment(assignment: TAgentAssignmentApi, runs: TAgentRunApi[] = []): TAgentAssignment {
  const assignmentRuns = [...runs]
    .filter((run) => run.assignment === assignment.id)
    .sort(
      (left: TAgentRunApi, right: TAgentRunApi) =>
        new Date(right.started_at).getTime() - new Date(left.started_at).getTime()
    );

  return {
    id: assignment.id,
    agentRef: assignment.agent_ref,
    agentName: formatAgentName(assignment.agent_ref),
    assignmentType: mapAssignmentType(assignment.assignment_type),
    status: mapAssignmentStatus(assignment.status),
    createdAt: assignment.created_at,
    desiredState: `Assigned to ${assignment.agent_ref}`,
    observedState: buildObservedState(assignment, runs),
    lastStatusUpdateAt: assignment.updated_at,
    runs: assignmentRuns.map(mapAgentRun),
  };
}

export function mapAttentionItem(item: TAgentAttentionItemApi): TAttentionQueueItem {
  const details = item.details ?? {};
  const driftType = item.drift_type;
  const verdict = driftType === "orphaned_run" ? "escalated" : "flagged";

  return {
    id: item.id,
    workItemId: String(details.work_item_id ?? item.entity_id),
    workItemIdentifier: String(details.work_item_identifier ?? item.entity_id),
    workItemTitle: String(details.work_item_title ?? `${item.entity_type} drift`),
    agentRef: String(details.agent_ref ?? "unknown-agent"),
    agentName: formatAgentName(String(details.agent_ref ?? "unknown-agent")),
    assignmentType: mapAssignmentType(String(details.assignment_type ?? "development")),
    verdict,
    verdictReason: String(details.reason ?? details.message ?? `${driftType.replace(/_/g, " ")} detected`),
    runId: String(details.run_id ?? item.entity_id),
    flaggedAt: item.created_at,
    dispositionStatus: "pending",
  };
}

export function mapSyncStatus(apiStatus: TAgentSyncStatusApi): TSyncStatusData {
  const lastSyncAt = apiStatus.last_outbox_delivery_at ?? apiStatus.last_reconciliation_at ?? undefined;
  const pendingOutbox = apiStatus.pending_outbox_count ?? 0;

  let status: TSyncStatus = "unknown";
  if (lastSyncAt) {
    const ageMs = Date.now() - new Date(lastSyncAt).getTime();
    if (ageMs >= DISCONNECTED_SYNC_THRESHOLD_MS) {
      status = "disconnected";
    } else if (
      ageMs >= STALE_SYNC_THRESHOLD_MS ||
      apiStatus.stale_assignment_count > 0 ||
      apiStatus.orphaned_run_count > 0
    ) {
      status = "stale";
    } else {
      status = "connected";
    }
  } else if (pendingOutbox > 0) {
    status = "stale";
  } else {
    status = "connected";
  }

  return {
    status,
    lastSyncAt,
    pendingOutbox,
  };
}

export function buildOverviewStats(
  assignments: TAgentAssignmentApi[],
  runs: TAgentRunApi[],
  syncStatus?: TAgentSyncStatusApi
): TAgentOverviewStats {
  const activeRuns = runs.filter((run) => !run.completed_at).length;
  const driftCount = (syncStatus?.stale_assignment_count ?? 0) + (syncStatus?.orphaned_run_count ?? 0);
  const totalAssignments = assignments.length;
  const escalationRate = totalAssignments > 0 ? Math.round((driftCount / totalAssignments) * 100) : 0;
  const completedRuns = runs.filter((run) => run.completed_at).length;
  const acceptanceRate =
    completedRuns > 0 ? Math.max(0, Math.round(((completedRuns - driftCount) / completedRuns) * 100)) : 0;

  return {
    totalAssignments,
    activeRuns,
    acceptanceRate,
    escalationRate,
  };
}

export function buildActivityFeed(assignments: TAgentAssignment[], runs: TAgentRunApi[]): TAgentActivityItem[] {
  const activity: TAgentActivityItem[] = [];

  assignments.slice(0, 5).forEach((assignment) => {
    activity.push({
      id: `assignment-${assignment.id}`,
      timestamp: assignment.createdAt,
      message: `Started ${assignment.assignmentType} assignment`,
      agentName: assignment.agentName,
      workItemIdentifier: assignment.agentRef,
      type: "assignment",
    });
  });

  runs.slice(0, 5).forEach((run) => {
    activity.push({
      id: `run-${run.id}`,
      timestamp: run.completed_at ?? run.started_at,
      message: run.completed_at ? `Run ${run.outcome}` : "Run started",
      agentName: formatAgentName(run.agent_ref),
      workItemIdentifier: run.agent_ref,
      type: "run",
    });
  });

  return activity
    .toSorted(
      (left: TAgentActivityItem, right: TAgentActivityItem) =>
        new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime()
    )
    .slice(0, 5);
}
