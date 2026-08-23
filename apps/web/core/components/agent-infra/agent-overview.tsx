/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Activity, AlertTriangle, Bot, CheckCircle2, PlayCircle } from "lucide-react";
import { Loader } from "@plane/ui";
import { AttentionQueue } from "./attention-queue";
import { StatCard } from "./stat-card";
import { SyncStatus } from "./sync-status";
import type { TAgentActivityItem, TAgentOverviewStats, TSyncStatusData } from "./mock-data";
import { useAgentInfraOverview } from "@/hooks/use-agent-infra";
import { formatRelativeTime } from "./mock-data";

type TAgentOverviewProps = {
  workspaceSlug?: string;
  projectId?: string;
  stats?: TAgentOverviewStats;
  activity?: TAgentActivityItem[];
  syncStatus?: TSyncStatusData;
  isLoading?: boolean;
  showAttentionQueue?: boolean;
  showSyncStatus?: boolean;
};

export function AgentOverview(props: TAgentOverviewProps) {
  const {
    workspaceSlug,
    projectId,
    stats: statsProp,
    activity: activityProp,
    syncStatus: syncStatusProp,
    isLoading: isLoadingProp = false,
    showAttentionQueue = true,
    showSyncStatus = true,
  } = props;

  const {
    stats: fetchedStats,
    syncStatus: fetchedSyncStatus,
    activity: fetchedActivity,
    isLoading: isFetching,
  } = useAgentInfraOverview(workspaceSlug, projectId);

  const stats = statsProp ?? fetchedStats;
  const activity = activityProp ?? fetchedActivity ?? [];
  const syncStatus = syncStatusProp ?? fetchedSyncStatus;
  const isLoading = isLoadingProp || Boolean(workspaceSlug && projectId && isFetching && !stats);

  if (isLoading || !stats) {
    return (
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {["pending", "running", "completed", "attention"].map((skeleton) => (
            <StatCard key={skeleton} label="" value="" icon={Bot} isLoading />
          ))}
        </div>
        <Loader className="space-y-3">
          <Loader.Item height="200px" />
          <Loader.Item height="280px" />
        </Loader>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-18 font-semibold text-primary">Agent infrastructure</h2>
        <p className="mt-1 text-13 text-tertiary">Monitor agent assignments, runs, and reviews across this project.</p>
      </div>

      {showSyncStatus && (
        <SyncStatus
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          status={syncStatus?.status}
          lastSyncAt={syncStatus?.lastSyncAt}
          pendingOutbox={syncStatus?.pendingOutbox}
        />
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total assignments"
          value={stats.totalAssignments}
          icon={Bot}
          description="All time in this project"
        />
        <StatCard label="Active runs" value={stats.activeRuns} icon={PlayCircle} description="Currently executing" />
        <StatCard
          label="Acceptance rate"
          value={`${stats.acceptanceRate}%`}
          icon={CheckCircle2}
          description="Reviews accepted on first pass"
          trend={{ value: "+4% vs last week", positive: true }}
        />
        <StatCard
          label="Escalation rate"
          value={`${stats.escalationRate}%`}
          icon={AlertTriangle}
          description="Runs escalated for human review"
          trend={{ value: "-2% vs last week", positive: true }}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-lg border border-subtle bg-surface-1 p-4">
          <div className="mb-4 flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent-primary" />
            <h3 className="text-14 font-semibold text-primary">Recent activity</h3>
          </div>

          {activity.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
              <Activity className="h-8 w-8 text-tertiary" />
              <p className="text-13 font-medium text-secondary">No recent activity</p>
              <p className="text-11 text-tertiary">Agent events will show up here as they happen.</p>
            </div>
          ) : (
            <div className="space-y-1">
              {activity.map((item) => (
                <ActivityFeedItem key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>

        {showAttentionQueue && (
          <div className="rounded-lg border border-subtle bg-surface-1 p-4">
            <AttentionQueue workspaceSlug={workspaceSlug} projectId={projectId} />
          </div>
        )}
      </div>
    </div>
  );
}

function ActivityFeedItem(props: { item: TAgentActivityItem }) {
  const { item } = props;

  const typeColors: Record<TAgentActivityItem["type"], string> = {
    assignment: "bg-accent-subtle text-accent-primary",
    run: "bg-green-50 text-success-primary",
    review: "bg-amber-50 text-amber-600",
    disposition: "bg-layer-2 text-secondary",
  };

  return (
    <div className="flex items-start gap-3 rounded-md px-2 py-2.5 hover:bg-layer-2">
      <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${typeColors[item.type]}`}>
        <Activity className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-13 text-primary">
          <span className="font-medium">{item.agentName}</span> <span className="text-secondary">{item.message}</span>
        </p>
        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-11 text-tertiary">
          <span>{item.workItemIdentifier}</span>
          <span>·</span>
          <span>{formatRelativeTime(item.timestamp)}</span>
        </div>
      </div>
    </div>
  );
}
