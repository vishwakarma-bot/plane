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

type TDispositionActionType = "approved" | "rejected" | "rework";

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

const ACTION_LABELS: Record<TDispositionActionType, string> = {
  approved: "Approve this run",
  rejected: "Reject this run",
  rework: "Request rework",
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
  const [pendingAction, setPendingAction] = useState<TDispositionActionType | null>(null);
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const usesApi = Boolean(workspaceSlug && projectId && runId);

  const handleCancel = () => {
    setPendingAction(null);
    setReason("");
    setError(null);
  };

  const handleConfirm = async () => {
    if (!pendingAction || !reason.trim()) {
      return;
    }

    const callback = pendingAction === "approved" ? onApprove : pendingAction === "rejected" ? onReject : onRework;

    if (usesApi) {
      setIsSubmitting(true);
      setError(null);
      try {
        await agentInfraService.createDisposition(workspaceSlug!, projectId!, runId!, {
          disposition: pendingAction,
          reason: reason.trim(),
          reviewed_at: new Date().toISOString(),
        });
        setStatus(pendingAction);
        setPendingAction(null);
        setReason("");
        callback?.();
        onComplete?.(pendingAction);
      } catch {
        setError("Failed to submit disposition. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    setStatus(pendingAction);
    setPendingAction(null);
    setReason("");
    callback?.();
    onComplete?.(pendingAction);
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

  if (pendingAction) {
    return (
      <div className={`flex ${compact ? "flex-wrap gap-1.5" : "flex-col gap-2"}`}>
        <label htmlFor="disposition-rationale" className="text-11 font-medium text-secondary">
          {ACTION_LABELS[pendingAction]}
        </label>
        <textarea
          id="disposition-rationale"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          className="placeholder:text-quaternary focus:border-accent-primary min-h-20 rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary focus:outline-none"
          placeholder="Enter your rationale..."
        />
        <div className="flex flex-wrap items-center gap-1.5">
          <Button variant="neutral-primary" size="sm" disabled={isSubmitting} onClick={handleCancel}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" disabled={isSubmitting || !reason.trim()} onClick={handleConfirm}>
            Confirm
          </Button>
        </div>
        {isSubmitting && <span className="text-11 text-tertiary">Submitting…</span>}
        {error && <span className="text-11 text-danger-primary">{error}</span>}
      </div>
    );
  }

  return (
    <div className={`flex ${compact ? "flex-wrap gap-1.5" : "flex-col gap-2"}`}>
      <span className="text-11 font-medium text-secondary">Review disposition</span>
      <div className="flex flex-wrap items-center gap-1.5">
        <Button variant="primary" size="sm" disabled={isSubmitting} onClick={() => setPendingAction("approved")}>
          Approve
        </Button>
        <Button variant="outline-danger" size="sm" disabled={isSubmitting} onClick={() => setPendingAction("rejected")}>
          Reject
        </Button>
        <Button variant="outline-primary" size="sm" disabled={isSubmitting} onClick={() => setPendingAction("rework")}>
          Rework
        </Button>
      </div>
    </div>
  );
}
