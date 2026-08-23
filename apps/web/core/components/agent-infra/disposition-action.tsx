/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Badge, Button } from "@plane/ui";
import type { TReviewDispositionStatus } from "./mock-data";
import { DISPOSITION_STATUS_LABELS } from "./mock-data";

type TDispositionActionProps = {
  status: TReviewDispositionStatus;
  onApprove?: () => void;
  onReject?: () => void;
  onRework?: () => void;
  compact?: boolean;
};

export function DispositionAction(props: TDispositionActionProps) {
  const { status: initialStatus, onApprove, onReject, onRework, compact = false } = props;
  const [status, setStatus] = useState<TReviewDispositionStatus>(initialStatus);

  const handleAction = (nextStatus: TReviewDispositionStatus, callback?: () => void) => {
    setStatus(nextStatus);
    callback?.();
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
        <Button variant="primary" size="sm" onClick={() => handleAction("approved", onApprove)}>
          Approve
        </Button>
        <Button variant="outline-danger" size="sm" onClick={() => handleAction("rejected", onReject)}>
          Reject
        </Button>
        <Button variant="outline-primary" size="sm" onClick={() => handleAction("rework", onRework)}>
          Rework
        </Button>
      </div>
    </div>
  );
}
