/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TAssignmentType = "qa" | "dev" | "review" | "research";

export type TAssignmentStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type TRunOutcome = "success" | "failed" | "partial";

export type TAuthorizingReviewVerdict = "accepted" | "flagged" | "escalated";

export type TReviewDispositionStatus = "pending" | "approved" | "rejected" | "rework";

export type TAgentRef = {
  id: string;
  name: string;
  description?: string;
};

export type TAuthorizingReview = {
  id: string;
  verdict: TAuthorizingReviewVerdict;
  reason: string;
  reviewedAt: string;
};

export type TReviewDisposition = {
  id: string;
  status: TReviewDispositionStatus;
  resolvedAt?: string;
  resolvedBy?: string;
};

export type TAgentRun = {
  id: string;
  attempt: number;
  model: string;
  outcome: TRunOutcome;
  durationMs: number;
  tokenCount: number;
  costUsd: number;
  startedAt: string;
  completedAt?: string;
  isActive?: boolean;
  review?: TAuthorizingReview;
  disposition?: TReviewDisposition;
};

export type TAgentAssignment = {
  id: string;
  agentRef: string;
  agentName: string;
  assignmentType: TAssignmentType;
  status: TAssignmentStatus;
  createdAt: string;
  desiredState?: string;
  observedState?: string;
  lastStatusUpdateAt?: string;
  runs: TAgentRun[];
};

export type TSyncStatus = "connected" | "stale" | "disconnected" | "unknown";

export type TSyncStatusData = {
  status: TSyncStatus;
  lastSyncAt?: string;
  pendingOutbox?: number;
};

export type TAttentionQueueItem = {
  id: string;
  workItemId: string;
  workItemIdentifier: string;
  workItemTitle: string;
  agentRef: string;
  agentName: string;
  assignmentType: TAssignmentType;
  verdict: TAuthorizingReviewVerdict;
  verdictReason: string;
  runId: string;
  flaggedAt: string;
  dispositionStatus: TReviewDispositionStatus;
};

export type TAgentOverviewStats = {
  totalAssignments: number;
  activeRuns: number;
  acceptanceRate: number;
  escalationRate: number;
};

export type TAgentActivityItem = {
  id: string;
  timestamp: string;
  message: string;
  agentName: string;
  workItemIdentifier: string;
  type: "assignment" | "run" | "review" | "disposition";
};

export const MOCK_AGENTS: TAgentRef[] = [
  { id: "agent-qa-1", name: "QA Sentinel", description: "Automated QA and regression checks" },
  { id: "agent-dev-1", name: "Code Crafter", description: "Implementation and bug fixes" },
  { id: "agent-review-1", name: "Review Guardian", description: "Code review and quality gates" },
  { id: "agent-research-1", name: "Research Scout", description: "Discovery and spike work" },
];

export const MOCK_ASSIGNMENTS: TAgentAssignment[] = [
  {
    id: "asgn-1",
    agentRef: "agent-dev-1",
    agentName: "Code Crafter",
    assignmentType: "dev",
    status: "running",
    createdAt: "2026-08-22T10:15:00Z",
    desiredState: "Assigned to dev-engineer",
    observedState: "Running on claude-sonnet-4",
    lastStatusUpdateAt: "2026-08-22T11:02:00Z",
    runs: [
      {
        id: "run-1",
        attempt: 1,
        model: "claude-sonnet-4",
        outcome: "success",
        durationMs: 45200,
        tokenCount: 12450,
        costUsd: 0.18,
        startedAt: "2026-08-22T10:16:00Z",
        completedAt: "2026-08-22T10:16:45Z",
        review: {
          id: "rev-1",
          verdict: "accepted",
          reason: "Changes align with acceptance criteria and pass lint checks.",
          reviewedAt: "2026-08-22T10:17:12Z",
        },
      },
      {
        id: "run-2",
        attempt: 2,
        model: "claude-sonnet-4",
        outcome: "partial",
        durationMs: 68300,
        tokenCount: 18920,
        costUsd: 0.27,
        startedAt: "2026-08-22T11:02:00Z",
        completedAt: "2026-08-22T11:03:08Z",
        review: {
          id: "rev-2",
          verdict: "flagged",
          reason: "Missing edge-case handling for empty input states.",
          reviewedAt: "2026-08-22T11:03:45Z",
        },
        disposition: {
          id: "disp-1",
          status: "pending",
        },
      },
    ],
  },
  {
    id: "asgn-2",
    agentRef: "agent-qa-1",
    agentName: "QA Sentinel",
    assignmentType: "qa",
    status: "completed",
    createdAt: "2026-08-21T14:30:00Z",
    runs: [
      {
        id: "run-3",
        attempt: 1,
        model: "gpt-4.1",
        outcome: "success",
        durationMs: 32100,
        tokenCount: 8420,
        costUsd: 0.12,
        startedAt: "2026-08-21T14:31:00Z",
        completedAt: "2026-08-21T14:31:32Z",
        review: {
          id: "rev-3",
          verdict: "accepted",
          reason: "All test scenarios passed with expected coverage.",
          reviewedAt: "2026-08-21T14:32:10Z",
        },
      },
    ],
  },
  {
    id: "asgn-3",
    agentRef: "agent-review-1",
    agentName: "Review Guardian",
    assignmentType: "review",
    status: "failed",
    createdAt: "2026-08-20T09:00:00Z",
    runs: [
      {
        id: "run-4",
        attempt: 1,
        model: "claude-sonnet-4",
        outcome: "failed",
        durationMs: 12800,
        tokenCount: 3100,
        costUsd: 0.04,
        startedAt: "2026-08-20T09:01:00Z",
        completedAt: "2026-08-20T09:01:13Z",
        review: {
          id: "rev-4",
          verdict: "escalated",
          reason: "Potential security concern in authentication flow requires human review.",
          reviewedAt: "2026-08-20T09:01:48Z",
        },
        disposition: {
          id: "disp-2",
          status: "pending",
        },
      },
    ],
  },
  {
    id: "asgn-4",
    agentRef: "agent-qa-1",
    agentName: "QA Sentinel",
    assignmentType: "qa",
    status: "pending",
    createdAt: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    desiredState: "Assigned to qa-engineer",
    lastStatusUpdateAt: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    runs: [],
  },
  {
    id: "asgn-5",
    agentRef: "agent-dev-1",
    agentName: "Code Crafter",
    assignmentType: "dev",
    status: "running",
    createdAt: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
    desiredState: "Assigned to dev-engineer",
    observedState: "Running on gpt-4",
    lastStatusUpdateAt: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    runs: [
      {
        id: "run-6",
        attempt: 1,
        model: "gpt-4",
        outcome: "success",
        durationMs: 0,
        tokenCount: 4200,
        costUsd: 0.08,
        startedAt: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
        isActive: true,
      },
    ],
  },
  {
    id: "asgn-6",
    agentRef: "agent-research-1",
    agentName: "Research Scout",
    assignmentType: "research",
    status: "running",
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    desiredState: "Assigned to research-agent",
    observedState: "Completed on claude-sonnet-4",
    lastStatusUpdateAt: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    runs: [
      {
        id: "run-7",
        attempt: 1,
        model: "claude-sonnet-4",
        outcome: "success",
        durationMs: 720000,
        tokenCount: 15600,
        costUsd: 0.22,
        startedAt: new Date(Date.now() - 55 * 60 * 1000).toISOString(),
        completedAt: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
      },
    ],
  },
];

export const MOCK_SYNC_STATUS: TSyncStatusData = {
  status: "connected",
  lastSyncAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
  pendingOutbox: 0,
};

export const MOCK_SYNC_STATUS_STALE: TSyncStatusData = {
  status: "stale",
  lastSyncAt: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
  pendingOutbox: 2,
};

export const MOCK_SYNC_STATUS_DISCONNECTED: TSyncStatusData = {
  status: "disconnected",
  lastSyncAt: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
  pendingOutbox: 5,
};

export const MOCK_SYNC_STATUS_UNKNOWN: TSyncStatusData = {
  status: "unknown",
};

export const MOCK_ATTENTION_QUEUE: TAttentionQueueItem[] = [
  {
    id: "attn-1",
    workItemId: "wi-101",
    workItemIdentifier: "PROJ-42",
    workItemTitle: "Add input validation to signup form",
    agentRef: "agent-dev-1",
    agentName: "Code Crafter",
    assignmentType: "dev",
    verdict: "flagged",
    verdictReason: "Missing edge-case handling for empty input states.",
    runId: "run-2",
    flaggedAt: "2026-08-22T11:03:45Z",
    dispositionStatus: "pending",
  },
  {
    id: "attn-2",
    workItemId: "wi-88",
    workItemIdentifier: "PROJ-31",
    workItemTitle: "Refactor auth middleware for token refresh",
    agentRef: "agent-review-1",
    agentName: "Review Guardian",
    assignmentType: "review",
    verdict: "escalated",
    verdictReason: "Potential security concern in authentication flow requires human review.",
    runId: "run-4",
    flaggedAt: "2026-08-20T09:01:48Z",
    dispositionStatus: "pending",
  },
  {
    id: "attn-3",
    workItemId: "wi-55",
    workItemIdentifier: "PROJ-18",
    workItemTitle: "Implement rate limiting on public API",
    agentRef: "agent-research-1",
    agentName: "Research Scout",
    assignmentType: "research",
    verdict: "flagged",
    verdictReason: "Proposed approach may not scale under high concurrency.",
    runId: "run-5",
    flaggedAt: "2026-08-19T16:20:00Z",
    dispositionStatus: "rework",
  },
];

export const MOCK_OVERVIEW_STATS: TAgentOverviewStats = {
  totalAssignments: 24,
  activeRuns: 3,
  acceptanceRate: 78,
  escalationRate: 8,
};

export const MOCK_ACTIVITY_FEED: TAgentActivityItem[] = [
  {
    id: "act-1",
    timestamp: "2026-08-22T11:03:45Z",
    message: "Run flagged for human review",
    agentName: "Code Crafter",
    workItemIdentifier: "PROJ-42",
    type: "review",
  },
  {
    id: "act-2",
    timestamp: "2026-08-22T10:16:00Z",
    message: "Started dev assignment",
    agentName: "Code Crafter",
    workItemIdentifier: "PROJ-42",
    type: "assignment",
  },
  {
    id: "act-3",
    timestamp: "2026-08-21T14:32:10Z",
    message: "QA run accepted",
    agentName: "QA Sentinel",
    workItemIdentifier: "PROJ-37",
    type: "run",
  },
  {
    id: "act-4",
    timestamp: "2026-08-20T09:01:48Z",
    message: "Review escalated to attention queue",
    agentName: "Review Guardian",
    workItemIdentifier: "PROJ-31",
    type: "review",
  },
  {
    id: "act-5",
    timestamp: "2026-08-19T17:05:00Z",
    message: "Disposition marked as rework",
    agentName: "Research Scout",
    workItemIdentifier: "PROJ-18",
    type: "disposition",
  },
];

export const ASSIGNMENT_TYPE_LABELS: Record<TAssignmentType, string> = {
  qa: "QA",
  dev: "Dev",
  review: "Review",
  research: "Research",
};

export const ASSIGNMENT_STATUS_LABELS: Record<TAssignmentStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const RUN_OUTCOME_LABELS: Record<TRunOutcome, string> = {
  success: "Success",
  failed: "Failed",
  partial: "Partial",
};

export const REVIEW_VERDICT_LABELS: Record<TAuthorizingReviewVerdict, string> = {
  accepted: "Accepted",
  flagged: "Flagged",
  escalated: "Escalated",
};

export const DISPOSITION_STATUS_LABELS: Record<TReviewDispositionStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  rework: "Rework",
};

export function formatDuration(durationMs: number): string {
  if (durationMs < 1000) return `${durationMs}ms`;
  const seconds = Math.floor(durationMs / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

export function formatTokenCount(count: number): string {
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return count.toString();
}

export function formatCost(costUsd: number): string {
  return `$${costUsd.toFixed(2)}`;
}

export function formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

const REVIEW_STALE_THRESHOLD_MS = 15 * 60 * 1000;

export function formatRunningDuration(startedAt: string): string {
  const diffMs = Date.now() - new Date(startedAt).getTime();
  const diffMinutes = Math.max(1, Math.floor(diffMs / 60000));
  return `Running for ${diffMinutes}m`;
}

export function isReviewStale(run: TAgentRun): boolean {
  if (run.review || run.isActive || !run.completedAt) return false;
  const ageMs = Date.now() - new Date(run.completedAt).getTime();
  return ageMs >= REVIEW_STALE_THRESHOLD_MS;
}

const ASSIGNMENT_SYNC_STALE_THRESHOLD_MS = 30 * 60 * 1000;

export function isAssignmentAwaitingSync(assignment: TAgentAssignment): boolean {
  return assignment.status === "pending" && !assignment.observedState;
}

export function isAssignmentStateSynced(assignment: TAgentAssignment): boolean {
  if (!assignment.observedState) return false;
  const desiredState = assignment.desiredState ?? `Assigned to ${assignment.agentRef}`;
  return desiredState === assignment.observedState;
}

export function isAssignmentPendingSync(assignment: TAgentAssignment): boolean {
  if (!assignment.observedState) {
    return isAssignmentAwaitingSync(assignment);
  }
  const desiredState = assignment.desiredState ?? `Assigned to ${assignment.agentRef}`;
  return desiredState !== assignment.observedState;
}

export function isAssignmentSyncStale(assignment: TAgentAssignment): boolean {
  const reference = assignment.lastStatusUpdateAt ?? assignment.createdAt;
  const ageMs = Date.now() - new Date(reference).getTime();
  return ageMs >= ASSIGNMENT_SYNC_STALE_THRESHOLD_MS;
}

export function isAssignmentStale(assignment: TAgentAssignment): boolean {
  if (assignment.status !== "pending" || assignment.observedState) return false;
  const reference = assignment.lastStatusUpdateAt ?? assignment.createdAt;
  const ageMs = Date.now() - new Date(reference).getTime();
  return ageMs >= 2 * 60 * 60 * 1000;
}
