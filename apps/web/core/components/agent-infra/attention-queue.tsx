/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { AlertTriangle, Bot, Inbox } from "lucide-react";
import type { TBadgeVariant } from "@plane/ui";
import { Badge, Loader } from "@plane/ui";
import { DispositionAction } from "./disposition-action";
import type { TAttentionQueueItem, TReviewDispositionStatus } from "./mock-data";
import {
  ASSIGNMENT_TYPE_LABELS,
  MOCK_ATTENTION_QUEUE,
  formatRelativeTime,
} from "./mock-data";
import { ReviewBadge } from "./review-badge";

type TAttentionQueueProps = {
  items?: TAttentionQueueItem[];
  isLoading?: boolean;
};

export function AttentionQueue(props: TAttentionQueueProps) {
  const { items: itemsProp, isLoading = false } = props;
  const [items, setItems] = useState<TAttentionQueueItem[]>(itemsProp ?? MOCK_ATTENTION_QUEUE);

  const handleDisposition = (itemId: string, status: TReviewDispositionStatus) => {
    setItems((prev) =>
      prev.map((item) => (item.id === itemId ? { ...item, dispositionStatus: status } : item))
    );
  };

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

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-16 text-center">
        <Inbox className="h-10 w-10 text-tertiary" />
        <div>
          <p className="text-14 font-semibold text-primary">Attention queue is clear</p>
          <p className="mt-1 max-w-sm text-13 text-tertiary">
            Flagged and escalated agent reviews will appear here for human disposition.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-amber-500" />
        <div>
          <h3 className="text-14 font-semibold text-primary">Attention queue</h3>
          <p className="text-11 text-tertiary">
            {items.filter((item) => item.dispositionStatus === "pending").length} items awaiting review
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {items.map((item) => (
          <AttentionQueueItemCard key={item.id} item={item} onDisposition={handleDisposition} />
        ))}
      </div>
    </div>
  );
}

type TAttentionQueueItemCardProps = {
  item: TAttentionQueueItem;
  onDisposition: (itemId: string, status: TReviewDispositionStatus) => void;
};

function AttentionQueueItemCard(props: TAttentionQueueItemCardProps) {
  const { item, onDisposition } = props;

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
            <ReviewBadge verdict={item.verdict} />
            <Badge variant="outline-neutral" size="sm" disabled>
              {ASSIGNMENT_TYPE_LABELS[item.assignmentType]}
            </Badge>
            {item.dispositionStatus !== "pending" && (
              <Badge variant={dispositionVariant[item.dispositionStatus]} size="sm" disabled>
                {item.dispositionStatus}
              </Badge>
            )}
          </div>

          <button type="button" className="block text-left">
            <h4 className="text-14 font-semibold text-primary hover:text-accent-primary">{item.workItemTitle}</h4>
          </button>

          <div className="flex flex-wrap items-center gap-2 text-11 text-tertiary">
            <Bot className="h-3.5 w-3.5" />
            <span>{item.agentName}</span>
            <span>·</span>
            <span>{formatRelativeTime(item.flaggedAt)}</span>
          </div>

          <p className="rounded-md bg-layer-2 px-3 py-2 text-13 leading-5 text-secondary">{item.verdictReason}</p>
        </div>

        <div className="shrink-0 lg:w-56">
          <DispositionAction
            status={item.dispositionStatus}
            compact
            onApprove={() => onDisposition(item.id, "approved")}
            onReject={() => onDisposition(item.id, "rejected")}
            onRework={() => onDisposition(item.id, "rework")}
          />
        </div>
      </div>
    </div>
  );
}
