/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useSWRConfig } from "swr";
import { AlertTriangle, Bot, Inbox } from "lucide-react";
import type { TBadgeVariant } from "@plane/ui";
import { Badge, Loader } from "@plane/ui";
import { useAgentInfraAttentionItems } from "@/hooks/use-agent-infra";
import { DispositionAction } from "./disposition-action";
import type { TAttentionQueueItem, TProgressionOutcome, TReviewDispositionStatus } from "./mock-data";
import { ASSIGNMENT_TYPE_LABELS, PROGRESSION_OUTCOME_LABELS, formatRelativeTime } from "./mock-data";
import { ReviewBadge } from "./review-badge";

type TAttentionCategory = "all" | "review" | "progression" | "drift";

type TAttentionQueueProps = {
  workspaceSlug?: string;
  projectId?: string;
  items?: TAttentionQueueItem[];
  isLoading?: boolean;
  onSelectRun?: (runId: string) => void;
};

const CATEGORY_TABS: Array<{ id: TAttentionCategory; label: string }> = [
  { id: "all", label: "All" },
  { id: "review", label: "Reviews" },
  { id: "progression", label: "Progression" },
  { id: "drift", label: "Drift" },
];

const PROGRESSION_VARIANTS: Record<TProgressionOutcome, TBadgeVariant> = {
  auto_progress: "accent-success",
  awaiting_disposition: "accent-warning",
  blocked: "accent-destructive",
};

const REVIEW_DRIFT_TYPES = new Set(["review_flagged", "review_escalated"]);
const PROGRESSION_DRIFT_TYPES = new Set(["awaiting_disposition", "progression_blocked"]);

export function AttentionQueue(props: TAttentionQueueProps) {
  const { workspaceSlug, projectId, items: itemsProp, isLoading: isLoadingProp = false, onSelectRun } = props;
  const [activeCategory, setActiveCategory] = useState<TAttentionCategory>("all");
  const categoryParam = activeCategory === "all" ? undefined : activeCategory;
  const { mutate: globalMutate } = useSWRConfig();
  const {
    items: fetchedItems,
    isLoading: isFetching,
    mutate,
  } = useAgentInfraAttentionItems(workspaceSlug, projectId, categoryParam);
  const [items, setItems] = useState<TAttentionQueueItem[]>(itemsProp ?? fetchedItems ?? []);

  useEffect(() => {
    if (itemsProp) {
      setItems(itemsProp);
      return;
    }
    if (fetchedItems) {
      setItems(fetchedItems);
    }
  }, [itemsProp, fetchedItems]);

  const handleDispositionComplete = async (itemId: string, status: TReviewDispositionStatus) => {
    setItems((prev) => prev.map((item) => (item.id === itemId ? { ...item, dispositionStatus: status } : item)));
    if (workspaceSlug && projectId) {
      await mutate();
      globalMutate((key) => typeof key === "string" && key.includes("AGENT_INFRA"), undefined, { revalidate: true });
    }
  };

  const isLoading = isLoadingProp || Boolean(workspaceSlug && projectId && isFetching && !itemsProp);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <Loader className="space-y-3">
          <Loader.Item height="96px" />
          <Loader.Item height="96px" />
          <Loader.Item height="96px" />
        </Loader>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="text-amber-500 h-4 w-4" />
        <div>
          <h3 className="text-14 font-semibold text-primary">Attention queue</h3>
          <p className="text-11 text-tertiary">
            {items.filter((item) => item.dispositionStatus === "pending").length} items awaiting action
          </p>
        </div>
      </div>

      {!itemsProp && (
        <div className="inline-flex gap-1 self-start rounded-lg bg-surface-1 p-1">
          {CATEGORY_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveCategory(tab.id)}
              className={`rounded-md px-3 py-1.5 text-13 font-medium transition-colors ${
                activeCategory === tab.id
                  ? "bg-layer-2 text-primary"
                  : "text-tertiary hover:bg-layer-1 hover:text-secondary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-16 text-center">
          <Inbox className="h-10 w-10 text-tertiary" />
          <div>
            <p className="text-14 font-semibold text-primary">Attention queue is clear</p>
            <p className="mt-1 max-w-sm text-13 text-tertiary">
              Flagged reviews, progression blocks, and drift items will appear here.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <AttentionQueueItemCard
              key={item.id}
              item={item}
              workspaceSlug={workspaceSlug}
              projectId={projectId}
              onSelectRun={onSelectRun}
              onDispositionComplete={handleDispositionComplete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

type TAttentionQueueItemCardProps = {
  item: TAttentionQueueItem;
  workspaceSlug?: string;
  projectId?: string;
  onSelectRun?: (runId: string) => void;
  onDispositionComplete: (itemId: string, status: TReviewDispositionStatus) => void;
};

function AttentionQueueItemCard(props: TAttentionQueueItemCardProps) {
  const { item, workspaceSlug, projectId, onSelectRun, onDispositionComplete } = props;
  const isReviewItem = REVIEW_DRIFT_TYPES.has(item.driftType ?? "");
  const isProgressionItem = PROGRESSION_DRIFT_TYPES.has(item.driftType ?? "");

  const dispositionVariant: Record<TReviewDispositionStatus, TBadgeVariant> = {
    pending: "accent-warning",
    approved: "accent-success",
    rejected: "accent-destructive",
    rework: "accent-warning",
  };

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-sm bg-layer-2 px-1.5 py-0.5 text-11 font-medium text-tertiary">
              {item.workItemIdentifier}
            </span>
            {isReviewItem && <ReviewBadge verdict={item.verdict} />}
            {isProgressionItem && item.progressionOutcome && (
              <Badge variant={PROGRESSION_VARIANTS[item.progressionOutcome]} size="sm" disabled>
                {PROGRESSION_OUTCOME_LABELS[item.progressionOutcome]}
              </Badge>
            )}
            <Badge variant="outline-neutral" size="sm" disabled>
              {ASSIGNMENT_TYPE_LABELS[item.assignmentType]}
            </Badge>
            {item.dispositionStatus !== "pending" && (
              <Badge variant={dispositionVariant[item.dispositionStatus]} size="sm" disabled>
                {item.dispositionStatus}
              </Badge>
            )}
          </div>

          <button type="button" className="block text-left" onClick={() => onSelectRun?.(item.runId)}>
            <h4 className="text-14 font-semibold text-primary hover:text-accent-primary">{item.workItemTitle}</h4>
          </button>

          <div className="flex flex-wrap items-center gap-2 text-11 text-tertiary">
            <Bot className="h-3.5 w-3.5" />
            <span>{item.agentName}</span>
            <span>·</span>
            <span>{formatRelativeTime(item.flaggedAt)}</span>
          </div>

          <p className="rounded-md bg-layer-2 px-3 py-2 text-13 leading-5 text-secondary">
            {isProgressionItem && item.progressionReason ? item.progressionReason : item.verdictReason}
          </p>
        </div>

        {isReviewItem && (
          <div className="shrink-0 lg:w-56">
            <DispositionAction
              status={item.dispositionStatus}
              workspaceSlug={workspaceSlug}
              projectId={projectId}
              runId={item.runId}
              compact
              onComplete={(status) => onDispositionComplete(item.id, status)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
