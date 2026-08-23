/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Badge, Button } from "@plane/ui";
import agentInfraService from "@/services/agent-infra.service";
import type { TReviewDispositionStatus } from "./mock-data";
import { DISPOSITION_STATUS_LABELS } from "./mock-data";

type TDispositionActionProps = {
  status: TReviewDispositionStatus;
  workspaceSlug?: string;
  projectId?: string;
  runId?: string;
  onApprove?: () => void;
  onReject?: () => void;
  onRework?: () => void;
  onComplete?: (status: TReviewDispositionStatus) => void;
  compact?: boolean;
};

export function DispositionAction(props: TDispositionActionProps) {
  const {
    status: initialStatus,
    workspaceSlug,
    projectId,
    runId,
    onApprove,
    onReject,
    onRework,
    onComplete,
    compact = false,
  } = props;
  const [status, setStatus] = useState<TReviewDispositionStatus>(initialStatus);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const usesApi = Boolean(workspaceSlug && projectId && runId);

  const handleAction = async (nextStatus: "approved" | "rejected" | "rework", callback?: () => void) => {
    if (usesApi) {
      setIsSubmitting(true);
      setError(null);
      try {
        await agentInfraService.createDisposition(workspaceSlug!, projectId!, runId!, {
          disposition: nextStatus,
          reason: "Reviewed via agent infrastructure UI",
          reviewed_at: new Date().toISOString(),
        });
        setStatus(nextStatus);
        callback?.();
        onComplete?.(nextStatus);
      } catch {
        setError("Failed to submit disposition. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    setStatus(nextStatus);
    callback?.();
    onComplete?.(nextStatus);
  };

  if (status !== "pending") {
    const variant =
      status === "approved" ? "accent-success" : status === "rejected" ? "accent-destructive" : "accent-warning";

    return (
      <div className="flex items-center gap-2">
        <span className="text-11 text-tertiary">Disposition</span>
        <Badge variant={variant} size="sm" disabled>
          {DISPOSITION_STATUS_LABELS[status]}
        </Badge>
      </div>
    );
  }

  return (
    <div className={`flex ${compact ? "flex-wrap gap-1.5" : "flex-col gap-2"}`}>
      <span className="text-11 font-medium text-secondary">Review disposition</span>
      <div className="flex flex-wrap items-center gap-1.5">
        <Button variant="primary" size="sm" disabled={isSubmitting} onClick={() => handleAction("approved", onApprove)}>
          Approve
        </Button>
        <Button
          variant="outline-danger"
          size="sm"
          disabled={isSubmitting}
          onClick={() => handleAction("rejected", onReject)}
        >
          Reject
        </Button>
        <Button
          variant="outline-primary"
          size="sm"
          disabled={isSubmitting}
          onClick={() => handleAction("rework", onRework)}
        >
          Rework
        </Button>
      </div>
      {isSubmitting && <span className="text-11 text-tertiary">Submitting…</span>}
      {error && <span className="text-11 text-danger-primary">{error}</span>}
    </div>
  );
}
