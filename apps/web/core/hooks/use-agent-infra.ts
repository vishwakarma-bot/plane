/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
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

const staleAwareSwrOptions = {
  ...swrOptions,
  keepPreviousData: true,
};

const runLedgerSwrOptions = {
  keepPreviousData: true,
  revalidateOnFocus: true,
  errorRetryCount: 3,
};

function useStaleSwrMeta<T>(data: T | undefined, error: unknown) {
  const lastFetchedAtRef = useRef<Date | undefined>();

  if (data !== undefined && data !== null && !error) {
    lastFetchedAtRef.current = new Date();
  }

  return {
    isStale: Boolean(data && error),
    lastFetchedAt: data ? lastFetchedAtRef.current : undefined,
  };
}

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
    staleAwareSwrOptions
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
    staleAwareSwrOptions
  );

  const {
    data: runsData,
    error: runsError,
    isLoading: runsLoading,
  } = useSWR(
    buildKey("AGENT_INFRA_RUNS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchRuns(workspaceSlug, projectId) : null,
    staleAwareSwrOptions
  );

  const assignments: TAgentAssignment[] | undefined =
    assignmentsData && runsData
      ? assignmentsData.results.map((assignment) => mapAgentAssignment(assignment, runsData.results))
      : undefined;

  const { isStale, lastFetchedAt } = useStaleSwrMeta(assignments, assignmentsError || runsError);

  return {
    assignments,
    isLoading: Boolean(workspaceSlug && projectId) && (assignmentsLoading || runsLoading),
    error: assignmentsError || runsError,
    isStale,
    lastFetchedAt,
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
    staleAwareSwrOptions
  );

  const {
    data: runsData,
    error: runsError,
    isLoading: runsLoading,
  } = useSWR(
    buildKey("AGENT_INFRA_RUNS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchRuns(workspaceSlug, projectId) : null,
    staleAwareSwrOptions
  );

  const hasApiData = Boolean(assignmentsData && runsData && rawSyncStatus);

  const stats: TAgentOverviewStats | undefined =
    hasApiData && assignmentsData && runsData
      ? buildOverviewStats(assignmentsData.results, runsData.results, rawSyncStatus)
      : undefined;

  const overviewError = syncError || assignmentsError || runsError;
  const { isStale, lastFetchedAt } = useStaleSwrMeta(hasApiData ? stats : undefined, overviewError);

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
    error: overviewError,
    isStale,
    lastFetchedAt,
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
    runLedgerSwrOptions
  );

  const runs: TRunLedgerItem[] | undefined = data ? data.results.map(mapRunLedgerItem) : undefined;
  const perPage = params?.per_page ?? 25;
  const hasMore = Boolean(data?.next_cursor && data.results.length >= perPage);
  const { isStale, lastFetchedAt } = useStaleSwrMeta(runs, error);

  return {
    runs,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    totalCount: data?.total_count,
    nextCursor: data?.next_cursor ?? null,
    hasMore,
    isStale,
    lastFetchedAt,
  };
}
