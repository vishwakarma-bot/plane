/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import type {
  TAgentActivityItem,
  TAgentAssignment,
  TAgentOverviewStats,
  TAttentionQueueItem,
  TRunDetailData,
  TRunLedgerItem,
  TSyncStatusData,
} from "@/components/agent-infra/mock-data";
import {
  buildActivityFeed,
  buildOverviewStats,
  mapAgentAssignment,
  mapAttentionItem,
  mapRunDetail,
  mapRunLedgerItem,
  mapSyncStatus,
} from "@/services/agent-infra.mappers";
import agentInfraService, { type TRunLedgerParams } from "@/services/agent-infra.service";

const swrOptions = {
  revalidateOnFocus: false,
  shouldRetryOnError: false,
};

function buildKey(prefix: string, workspaceSlug?: string, projectId?: string) {
  return workspaceSlug && projectId ? `${prefix}_${workspaceSlug}_${projectId}` : null;
}

function buildRunDetailKey(workspaceSlug?: string, projectId?: string, runId?: string) {
  return workspaceSlug && projectId && runId ? `AGENT_INFRA_RUN_DETAIL_${workspaceSlug}_${projectId}_${runId}` : null;
}

function buildRunLedgerKey(workspaceSlug?: string, projectId?: string, params?: TRunLedgerParams) {
  if (!workspaceSlug || !projectId) return null;
  const paramKey = params
    ? JSON.stringify({
        cursor: params.cursor,
        per_page: params.per_page,
        outcome: params.outcome,
        progression_outcome: params.progression_outcome,
        agent_ref: params.agent_ref,
        assignment_id: params.assignment_id,
        work_item_id: params.work_item_id,
      })
    : "";
  return `AGENT_INFRA_RUN_LEDGER_${workspaceSlug}_${projectId}_${paramKey}`;
}

export function useAgentInfraSyncStatus(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("AGENT_INFRA_SYNC_STATUS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchSyncStatus(workspaceSlug, projectId) : null,
    swrOptions
  );

  const syncStatus: TSyncStatusData | undefined = data ? mapSyncStatus(data) : undefined;

  return {
    syncStatus,
    rawSyncStatus: data,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useAgentInfraAssignments(workspaceSlug?: string, projectId?: string) {
  const {
    data: assignmentsData,
    error: assignmentsError,
    isLoading: assignmentsLoading,
  } = useSWR(
    buildKey("AGENT_INFRA_ASSIGNMENTS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchAssignments(workspaceSlug, projectId) : null,
    swrOptions
  );

  const {
    data: runsData,
    error: runsError,
    isLoading: runsLoading,
  } = useSWR(
    buildKey("AGENT_INFRA_RUNS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchRuns(workspaceSlug, projectId) : null,
    swrOptions
  );

  const assignments: TAgentAssignment[] | undefined =
    assignmentsData && runsData
      ? assignmentsData.results.map((assignment) => mapAgentAssignment(assignment, runsData.results))
      : undefined;

  return {
    assignments,
    isLoading: Boolean(workspaceSlug && projectId) && (assignmentsLoading || runsLoading),
    error: assignmentsError || runsError,
  };
}

function buildAttentionKey(workspaceSlug?: string, projectId?: string, category?: string) {
  if (!workspaceSlug || !projectId) return null;
  return `AGENT_INFRA_ATTENTION_ITEMS_${workspaceSlug}_${projectId}_${category ?? "all"}`;
}

export function useAgentInfraAttentionItems(workspaceSlug?: string, projectId?: string, category?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildAttentionKey(workspaceSlug, projectId, category),
    workspaceSlug && projectId
      ? () => agentInfraService.fetchAttentionItems(workspaceSlug, projectId, category ? { category } : undefined)
      : null,
    swrOptions
  );

  const items: TAttentionQueueItem[] | undefined = data ? data.results.map(mapAttentionItem) : undefined;

  const resolveItem = async (itemId: string) => {
    if (!workspaceSlug || !projectId || error) return;
    await agentInfraService.resolveAttentionItem(workspaceSlug, projectId, itemId);
    await mutate();
  };

  return {
    items,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    resolveItem,
    mutate,
  };
}

export function useAgentInfraOverview(workspaceSlug?: string, projectId?: string) {
  const {
    syncStatus,
    rawSyncStatus,
    isLoading: syncLoading,
    error: syncError,
  } = useAgentInfraSyncStatus(workspaceSlug, projectId);

  const {
    data: assignmentsData,
    error: assignmentsError,
    isLoading: assignmentsLoading,
  } = useSWR(
    buildKey("AGENT_INFRA_ASSIGNMENTS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchAssignments(workspaceSlug, projectId) : null,
    swrOptions
  );

  const {
    data: runsData,
    error: runsError,
    isLoading: runsLoading,
  } = useSWR(
    buildKey("AGENT_INFRA_RUNS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchRuns(workspaceSlug, projectId) : null,
    swrOptions
  );

  const hasApiData = Boolean(assignmentsData && runsData && rawSyncStatus);

  const stats: TAgentOverviewStats | undefined =
    hasApiData && assignmentsData && runsData
      ? buildOverviewStats(assignmentsData.results, runsData.results, rawSyncStatus)
      : undefined;

  const mappedAssignments =
    hasApiData && assignmentsData && runsData
      ? assignmentsData.results.map((assignment) => mapAgentAssignment(assignment, runsData.results))
      : undefined;

  const activity: TAgentActivityItem[] | undefined =
    hasApiData && mappedAssignments && runsData ? buildActivityFeed(mappedAssignments, runsData.results) : undefined;

  return {
    stats,
    syncStatus,
    activity,
    isLoading:
      Boolean(workspaceSlug && projectId) &&
      (syncLoading ||
        assignmentsLoading ||
        runsLoading ||
        (!hasApiData && !syncError && !assignmentsError && !runsError)),
    error: syncError || assignmentsError || runsError,
  };
}

export function useAgentRunDetail(workspaceSlug?: string, projectId?: string, runId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildRunDetailKey(workspaceSlug, projectId, runId),
    workspaceSlug && projectId && runId
      ? () => agentInfraService.fetchRunDetail(workspaceSlug, projectId, runId)
      : null,
    swrOptions
  );

  const runDetail: TRunDetailData | undefined = data ? mapRunDetail(data) : undefined;

  return {
    runDetail,
    isLoading: Boolean(workspaceSlug && projectId && runId) && isLoading,
    error,
    mutate,
  };
}

export function useAgentRunLedger(workspaceSlug?: string, projectId?: string, params?: TRunLedgerParams) {
  const { data, error, isLoading } = useSWR(
    buildRunLedgerKey(workspaceSlug, projectId, params),
    workspaceSlug && projectId ? () => agentInfraService.fetchRunLedger(workspaceSlug, projectId, params) : null,
    swrOptions
  );

  const runs: TRunLedgerItem[] | undefined = data ? data.results.map(mapRunLedgerItem) : undefined;

  return {
    runs,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    totalCount: data?.total_count,
    nextCursor: data?.next_cursor ?? null,
  };
}

// --- P7: Authorization Policy hooks ---

export function useAuthorizationPolicies(workspaceSlug?: string, projectId?: string, params?: Record<string, string>) {
  const paramKey = params ? JSON.stringify(params) : "";
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("AGENT_INFRA_POLICIES", workspaceSlug, projectId)
      ? `AGENT_INFRA_POLICIES_${workspaceSlug}_${projectId}_${paramKey}`
      : null,
    workspaceSlug && projectId ? () => agentInfraService.fetchPolicies(workspaceSlug, projectId, params) : null,
    swrOptions
  );

  return {
    policies: data?.results,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useAuthorizationPolicy(workspaceSlug?: string, projectId?: string, policyId?: string) {
  const key =
    workspaceSlug && projectId && policyId ? `AGENT_INFRA_POLICY_${workspaceSlug}_${projectId}_${policyId}` : null;
  const { data, error, isLoading, mutate } = useSWR(
    key,
    workspaceSlug && projectId && policyId
      ? () => agentInfraService.fetchPolicy(workspaceSlug, projectId, policyId)
      : null,
    swrOptions
  );

  return {
    policy: data,
    isLoading: Boolean(workspaceSlug && projectId && policyId) && isLoading,
    error,
    mutate,
  };
}

export function usePolicyDecisions(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading } = useSWR(
    buildKey("AGENT_INFRA_DECISIONS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchDecisions(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    decisions: data?.results,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
  };
}

export function useActionApprovals(workspaceSlug?: string, projectId?: string, params?: Record<string, string>) {
  const paramKey = params ? JSON.stringify(params) : "";
  const { data, error, isLoading, mutate } = useSWR(
    workspaceSlug && projectId ? `AGENT_INFRA_APPROVALS_${workspaceSlug}_${projectId}_${paramKey}` : null,
    workspaceSlug && projectId ? () => agentInfraService.fetchApprovals(workspaceSlug, projectId, params) : null,
    swrOptions
  );

  return {
    approvals: data?.results,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useEmergencyDenies(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("AGENT_INFRA_EMERGENCY_DENIES", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchEmergencyDenies(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    emergencyDenies: data?.results,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useSoDConstraints(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading } = useSWR(
    buildKey("AGENT_INFRA_SOD_CONSTRAINTS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchSoDConstraints(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    constraints: data?.results,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
  };
}
