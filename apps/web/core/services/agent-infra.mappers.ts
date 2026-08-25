/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import {
  DRIFT_TYPE_LABELS,
  PROGRESSION_OUTCOME_LABELS,
  formatShortId,
  type TAgentActivityItem,
  type TAgentAssignment,
  type TAgentOverviewStats,
  type TAgentRun,
  type TAssignmentStatus,
  type TAssignmentType,
  type TAttentionQueueItem,
  type TAuthorizingReviewVerdict,
  type TProgressionOutcome,
  type TReviewDispositionStatus,
  type TRunDetailData,
  type TRunLedgerItem,
  type TRunOutcome,
  type TSyncStatus,
  type TSyncStatusData,
} from "@/components/agent-infra/mock-data";
import type {
  TAgentAssignmentApi,
  TAgentAttentionItemApi,
  TAgentRunApi,
  TAgentRunDetailApi,
  TAgentSyncStatusApi,
  TRunLedgerItemApi,
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
  failure: "failure",
  failed: "failure",
  partial: "partial",
  blocked: "failure",
};

const PROGRESSION_OUTCOME_MAP: Record<string, TProgressionOutcome> = {
  auto_progress: "auto_progress",
  awaiting_disposition: "awaiting_disposition",
  blocked: "blocked",
};

const REVIEW_VERDICT_MAP: Record<string, TAuthorizingReviewVerdict> = {
  accepted: "accepted",
  flagged: "flagged",
  escalated: "escalated",
};

const DISPOSITION_STATUS_MAP: Record<string, TReviewDispositionStatus> = {
  pending: "pending",
  approved: "approved",
  rejected: "rejected",
  rework: "rework",
};

const REVIEW_ATTENTION_DRIFT_TYPES = new Set(["review_flagged", "review_escalated"]);

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

function mapProgressionOutcome(value?: string | null): TProgressionOutcome | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return PROGRESSION_OUTCOME_MAP[value] ?? undefined;
}

function mapReviewVerdict(value?: string | null): TAuthorizingReviewVerdict | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return REVIEW_VERDICT_MAP[value] ?? "flagged";
}

function mapDispositionStatus(value?: string | null): TReviewDispositionStatus | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return DISPOSITION_STATUS_MAP[value] ?? "pending";
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
    .toSorted(
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
    .toSorted(
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

function buildAttentionTitle(driftType: string, details: Record<string, unknown>, entityType: string): string {
  if (details.work_item_title) {
    return String(details.work_item_title);
  }

  const progressionOutcome = details.progression_outcome ? String(details.progression_outcome) : "";
  if (progressionOutcome && progressionOutcome in PROGRESSION_OUTCOME_LABELS) {
    return PROGRESSION_OUTCOME_LABELS[progressionOutcome as TProgressionOutcome];
  }

  if (DRIFT_TYPE_LABELS[driftType]) {
    return DRIFT_TYPE_LABELS[driftType];
  }

  if (driftType) {
    return driftType.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }

  return `${entityType.replace(/_/g, " ")} drift`;
}

export function mapAttentionItem(item: TAgentAttentionItemApi): TAttentionQueueItem {
  const details = item.details ?? {};
  const driftType = item.drift_type;
  const isReviewAttention = REVIEW_ATTENTION_DRIFT_TYPES.has(driftType);
  const isProgressionAttention = driftType === "awaiting_disposition" || driftType === "progression_blocked";
  const runId = String(details.run_id ?? item.entity_id);
  const agentRef = details.agent_ref ? String(details.agent_ref) : "";
  const verdict = isReviewAttention
    ? (mapReviewVerdict(String(details.verdict ?? driftType.replace("review_", ""))) ?? "flagged")
    : driftType === "orphaned_run"
      ? "escalated"
      : "flagged";

  return {
    id: item.id,
    workItemId: String(details.work_item_id ?? runId),
    workItemIdentifier: details.work_item_identifier ? String(details.work_item_identifier) : formatShortId(runId),
    workItemTitle: buildAttentionTitle(driftType, details, item.entity_type),
    agentRef: agentRef || runId,
    agentName: agentRef ? formatAgentName(agentRef) : `Run ${formatShortId(runId)}`,
    assignmentType: mapAssignmentType(String(details.assignment_type ?? "development")),
    verdict,
    verdictReason: isReviewAttention
      ? String(details.reason ?? details.message ?? DRIFT_TYPE_LABELS[driftType] ?? "")
      : String(details.reason ?? details.message ?? ""),
    runId,
    flaggedAt: item.created_at,
    dispositionStatus: isReviewAttention
      ? (mapDispositionStatus(String(details.disposition ?? "pending")) ?? "pending")
      : "pending",
    driftType,
    progressionOutcome: isProgressionAttention
      ? mapProgressionOutcome(
          String(
            details.progression_outcome ?? (driftType === "progression_blocked" ? "blocked" : "awaiting_disposition")
          )
        )
      : undefined,
    progressionReason: isProgressionAttention
      ? String(details.progression_reason ?? DRIFT_TYPE_LABELS[driftType] ?? "")
      : undefined,
  };
}

export function mapRunDetail(api: TAgentRunDetailApi): TRunDetailData {
  return {
    id: api.id,
    agentRef: api.agent_ref,
    modelUsed: api.model_used,
    outcome: mapRunOutcome(api.outcome),
    startedAt: api.started_at,
    completedAt: api.completed_at ?? undefined,
    tokensIn: api.tokens_in ?? 0,
    tokensOut: api.tokens_out ?? 0,
    costUsd: Number(api.cost_usd ?? 0),
    correlationId: api.correlation_id ?? "",
    progressionOutcome: mapProgressionOutcome(api.progression_outcome),
    progressionReason: api.progression_reason,
    progressionEvaluatedAt: api.progression_evaluated_at,
    review: api.authorizing_review
      ? {
          id: api.authorizing_review.id,
          verdict: mapReviewVerdict(api.authorizing_review.verdict) ?? "flagged",
          reason: api.authorizing_review.reason,
          reviewedAt: api.authorizing_review.reviewed_at,
          reviewerModel: api.authorizing_review.reviewer_model,
        }
      : api.authorizing_review,
    disposition: api.review_disposition
      ? {
          id: api.review_disposition.id,
          status: mapDispositionStatus(api.review_disposition.disposition) ?? "pending",
          resolvedAt: api.review_disposition.reviewed_at,
          resolvedBy: api.review_disposition.reviewer,
        }
      : api.review_disposition,
    artifacts: (api.artifact_references ?? []).map((artifact) => ({
      id: artifact.id,
      artifactType: artifact.artifact_type,
      storageRef: artifact.storage_ref,
      hash: artifact.hash,
      classification: artifact.classification,
      expiresAt: artifact.expires_at,
    })),
    contextManifests: (api.context_manifests ?? []).map((manifest) => ({
      id: manifest.id,
      knowledgeVersionId: manifest.knowledge_version_id,
      sourceName: manifest.source_name,
      versionNumber: manifest.version_number,
      boundAt: manifest.bound_at,
    })),
    assignmentSummary: {
      id: api.assignment_summary.id,
      agentRef: api.assignment_summary.agent_ref,
      assignmentType: mapAssignmentType(api.assignment_summary.assignment_type),
      status: mapAssignmentStatus(api.assignment_summary.status),
      workItemId: api.assignment_summary.work_item_id,
    },
  };
}

export function mapRunLedgerItem(api: TRunLedgerItemApi): TRunLedgerItem {
  return {
    id: api.id,
    agentRef: api.agent_ref,
    modelUsed: api.model_used,
    outcome: mapRunOutcome(api.outcome),
    progressionOutcome: mapProgressionOutcome(api.progression_outcome),
    startedAt: api.started_at,
    completedAt: api.completed_at ?? undefined,
    tokensIn: api.tokens_in ?? 0,
    tokensOut: api.tokens_out ?? 0,
    costUsd: Number(api.cost_usd ?? 0),
    correlationId: api.correlation_id ?? "",
    verdict: mapReviewVerdict(api.verdict),
    disposition: mapDispositionStatus(api.disposition),
    workItemId: api.work_item_id,
    assignmentId: api.assignment,
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
  _syncStatus?: TAgentSyncStatusApi
): TAgentOverviewStats {
  const activeRuns = runs.filter((run) => !run.completed_at).length;
  const totalAssignments = assignments.length;
  const completedRuns = runs.filter((run) => run.completed_at);

  const acceptedRuns = completedRuns.filter(
    (run) => run.progression_outcome === "auto_progress" || run.outcome === "success"
  ).length;
  const escalatedRuns = completedRuns.filter(
    (run) => run.progression_outcome === "awaiting_disposition" || run.progression_outcome === "blocked"
  ).length;

  const acceptanceRate = completedRuns.length > 0 ? Math.round((acceptedRuns / completedRuns.length) * 100) : 0;
  const escalationRate = completedRuns.length > 0 ? Math.round((escalatedRuns / completedRuns.length) * 100) : 0;

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
