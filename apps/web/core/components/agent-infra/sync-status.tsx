/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Loader } from "@plane/ui";
import { useAgentInfraSyncStatus } from "@/hooks/use-agent-infra";
import { formatRelativeTime } from "./mock-data";

export type SyncStatus = "connected" | "stale" | "disconnected" | "unknown";

export interface SyncStatusProps {
  workspaceSlug?: string;
  projectId?: string;
  status?: SyncStatus;
  lastSyncAt?: string;
  pendingOutbox?: number;
}

const STALE_THRESHOLD_MS = 5 * 60 * 1000;
const DISCONNECTED_THRESHOLD_MS = 30 * 60 * 1000;

const STATUS_DOT: Record<SyncStatus, string> = {
  connected: "bg-green-500",
  stale: "bg-amber-500",
  disconnected: "bg-red-500",
  unknown: "bg-gray-400",
};

function resolveDisplayStatus(status: SyncStatus, lastSyncAt?: string): SyncStatus {
  if (status === "unknown" || !lastSyncAt) {
    return status;
  }

  const ageMs = Date.now() - new Date(lastSyncAt).getTime();
  if (ageMs >= DISCONNECTED_THRESHOLD_MS) return "disconnected";
  if (ageMs >= STALE_THRESHOLD_MS) return "stale";
  return "connected";
}

function statusLabel(status: SyncStatus, lastSyncAt?: string): string {
  switch (status) {
    case "connected":
      return "Synced";
    case "stale":
      return lastSyncAt ? `Stale (${formatRelativeTime(lastSyncAt)})` : "Stale";
    case "disconnected":
      return "Disconnected";
    default:
      return "Unknown";
  }
}

export function SyncStatus(props: SyncStatusProps) {
  const {
    workspaceSlug,
    projectId,
    status: statusProp,
    lastSyncAt: lastSyncAtProp,
    pendingOutbox: pendingOutboxProp,
  } = props;

  const shouldFetch = Boolean(workspaceSlug && projectId && statusProp === undefined);
  const { syncStatus, isLoading } = useAgentInfraSyncStatus(
    shouldFetch ? workspaceSlug : undefined,
    shouldFetch ? projectId : undefined
  );
  const status = statusProp ?? syncStatus?.status ?? "unknown";
  const lastSyncAt = lastSyncAtProp ?? syncStatus?.lastSyncAt;
  const pendingOutbox = pendingOutboxProp ?? syncStatus?.pendingOutbox ?? 0;

  if (shouldFetch && isLoading && !statusProp) {
    return (
      <div className="rounded-lg border border-subtle bg-surface-1 px-4 py-3">
        <Loader className="space-y-2">
          <Loader.Item height="14px" width="40%" />
          <Loader.Item height="12px" width="25%" />
        </Loader>
      </div>
    );
  }

  const displayStatus = resolveDisplayStatus(status, lastSyncAt);
  const label = statusLabel(displayStatus, lastSyncAt);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-subtle bg-surface-1 px-4 py-3">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${STATUS_DOT[displayStatus]}`} />
        <div className="min-w-0">
          <p className="text-13 font-medium text-primary">Development Center</p>
          <p className="text-11 text-tertiary">{label}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-11 text-tertiary">
        {lastSyncAt && displayStatus === "connected" && (
          <span>Last sync {formatRelativeTime(lastSyncAt)}</span>
        )}
        {pendingOutbox > 0 && (
          <span className="rounded-md bg-layer-2 px-2 py-0.5 text-secondary">
            {pendingOutbox} pending outbox
          </span>
        )}
      </div>
    </div>
  );
}
