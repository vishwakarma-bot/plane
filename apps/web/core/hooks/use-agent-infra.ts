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
  TSyncStatusData,
} from "@/components/agent-infra/mock-data";
import {
  MOCK_ACTIVITY_FEED,
  MOCK_ASSIGNMENTS,
  MOCK_ATTENTION_QUEUE,
  MOCK_OVERVIEW_STATS,
  MOCK_SYNC_STATUS,
} from "@/components/agent-infra/mock-data";
import {
  buildActivityFeed,
  buildOverviewStats,
  mapAgentAssignment,
  mapAttentionItem,
  mapSyncStatus,
} from "@/services/agent-infra.mappers";
import agentInfraService from "@/services/agent-infra.service";

const swrOptions = {
  revalidateOnFocus: false,
  shouldRetryOnError: false,
};

function buildKey(prefix: string, workspaceSlug?: string, projectId?: string) {
  return workspaceSlug && projectId ? `${prefix}_${workspaceSlug}_${projectId}` : null;
}

export function useAgentInfraSyncStatus(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("AGENT_INFRA_SYNC_STATUS", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () => agentInfraService.fetchSyncStatus(workspaceSlug, projectId)
      : null,
    swrOptions
  );

  const syncStatus: TSyncStatusData | undefined = data
    ? mapSyncStatus(data)
    : error
      ? MOCK_SYNC_STATUS
      : undefined;
  const isUsingMockData = Boolean(error) && !data;

  return {
    syncStatus,
    rawSyncStatus: data,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    isUsingMockData,
    mutate,
  };
}

export function useAgentInfraAssignments(workspaceSlug?: string, projectId?: string) {
  const { data: assignmentsData, error: assignmentsError, isLoading: assignmentsLoading } = useSWR(
    buildKey("AGENT_INFRA_ASSIGNMENTS", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () => agentInfraService.fetchAssignments(workspaceSlug, projectId)
      : null,
    swrOptions
  );

  const { data: runsData } = useSWR(
    buildKey("AGENT_INFRA_RUNS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchRuns(workspaceSlug, projectId) : null,
    swrOptions
  );

  const assignments: TAgentAssignment[] | undefined =
    assignmentsData?.results && runsData?.results
      ? assignmentsData.results.map((assignment) => mapAgentAssignment(assignment, runsData.results))
      : assignmentsError
        ? MOCK_ASSIGNMENTS
        : undefined;

  return {
    assignments,
    isLoading: Boolean(workspaceSlug && projectId) && assignmentsLoading,
    error: assignmentsError,
    isUsingMockData: Boolean(assignmentsError) && !assignmentsData,
  };
}

export function useAgentInfraAttentionItems(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("AGENT_INFRA_ATTENTION_ITEMS", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () => agentInfraService.fetchAttentionItems(workspaceSlug, projectId)
      : null,
    swrOptions
  );

  const items: TAttentionQueueItem[] | undefined = data?.results
    ? data.results.map(mapAttentionItem)
    : error
      ? MOCK_ATTENTION_QUEUE
      : undefined;

  const resolveItem = async (itemId: string) => {
    if (!workspaceSlug || !projectId || error) return;
    await agentInfraService.resolveAttentionItem(workspaceSlug, projectId, itemId);
    await mutate();
  };

  return {
    items,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    isUsingMockData: Boolean(error) && !data,
    resolveItem,
    mutate,
  };
}

export function useAgentInfraOverview(workspaceSlug?: string, projectId?: string) {
  const { syncStatus, rawSyncStatus, isLoading: syncLoading, error: syncError } = useAgentInfraSyncStatus(
    workspaceSlug,
    projectId
  );

  const { data: assignmentsData, error: assignmentsError, isLoading: assignmentsLoading } = useSWR(
    buildKey("AGENT_INFRA_ASSIGNMENTS", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () => agentInfraService.fetchAssignments(workspaceSlug, projectId)
      : null,
    swrOptions
  );

  const { data: runsData, error: runsError } = useSWR(
    buildKey("AGENT_INFRA_RUNS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => agentInfraService.fetchRuns(workspaceSlug, projectId) : null,
    swrOptions
  );

  const hasApiData = Boolean(assignmentsData && runsData && rawSyncStatus);
  const hasError = Boolean(syncError || assignmentsError || runsError);

  const stats: TAgentOverviewStats | undefined =
    hasApiData && assignmentsData && runsData
      ? buildOverviewStats(assignmentsData.results, runsData.results, rawSyncStatus)
      : hasError
        ? MOCK_OVERVIEW_STATS
        : undefined;

  const mappedAssignments =
    hasApiData && assignmentsData && runsData
      ? assignmentsData.results.map((assignment) => mapAgentAssignment(assignment, runsData.results))
      : undefined;

  const activity: TAgentActivityItem[] | undefined =
    hasApiData && mappedAssignments && runsData
      ? buildActivityFeed(mappedAssignments, runsData.results)
      : hasError
        ? MOCK_ACTIVITY_FEED
        : undefined;

  return {
    stats,
    syncStatus,
    activity,
    isLoading: Boolean(workspaceSlug && projectId) && (syncLoading || assignmentsLoading),
    isUsingMockData: !hasApiData && hasError,
  };
}
