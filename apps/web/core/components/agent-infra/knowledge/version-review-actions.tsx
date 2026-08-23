/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { CheckCircle, Clock, Eye, ShieldAlert, XCircle } from "lucide-react";
import { Button } from "@plane/propel/button";
import type { TKnowledgeVersion, TVersionStatus } from "./knowledge-types";

type TVersionReviewActionsProps = {
  version: TKnowledgeVersion;
  onStatusChange: (versionId: string, newStatus: TVersionStatus) => Promise<void>;
};

const STATUS_CONFIG: Record<TVersionStatus, { label: string; icon: React.ElementType; className: string }> = {
  draft: { label: "Draft", icon: Clock, className: "text-tertiary" },
  review: { label: "In Review", icon: Eye, className: "text-blue-600" },
  approved: { label: "Approved", icon: CheckCircle, className: "text-green-600" },
  rejected: { label: "Rejected", icon: XCircle, className: "text-red-600" },
  superseded: { label: "Superseded", icon: Clock, className: "text-amber-600" },
  quarantined: { label: "Quarantined", icon: ShieldAlert, className: "text-orange-600" },
};

const ALLOWED_TRANSITIONS: Record<TVersionStatus, TVersionStatus[]> = {
  draft: ["review", "rejected"],
  review: ["approved", "rejected", "draft"],
  approved: ["superseded", "quarantined"],
  rejected: ["draft"],
  superseded: [],
  quarantined: ["review", "rejected"],
};

export function VersionReviewActions(props: TVersionReviewActionsProps) {
  const { version, onStatusChange } = props;
  const [isSubmitting, setIsSubmitting] = useState(false);

  const currentConfig = STATUS_CONFIG[version.status];
  const Icon = currentConfig.icon;
  const allowedNext = ALLOWED_TRANSITIONS[version.status] ?? [];

  const handleTransition = useCallback(
    async (newStatus: TVersionStatus) => {
      setIsSubmitting(true);
      try {
        await onStatusChange(version.id, newStatus);
      } finally {
        setIsSubmitting(false);
      }
    },
    [onStatusChange, version.id]
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={`inline-flex items-center gap-1.5 text-12 font-medium ${currentConfig.className}`}>
        <Icon className="h-3.5 w-3.5" />
        {currentConfig.label}
      </span>

      {version.is_agent_generated && version.status === "quarantined" && (
        <span className="bg-orange-100 text-orange-800 dark:bg-orange-950/40 dark:text-orange-300 rounded-sm px-1.5 py-0.5 text-10 font-medium">
          Agent-generated — needs human review
        </span>
      )}

      {allowedNext.length > 0 && (
        <div className="flex items-center gap-1.5">
          {allowedNext.includes("review") && (
            <Button
              variant="neutral-primary"
              size="sm"
              disabled={isSubmitting}
              onClick={() => handleTransition("review")}
            >
              Submit for Review
            </Button>
          )}
          {allowedNext.includes("approved") && (
            <Button variant="primary" size="sm" disabled={isSubmitting} onClick={() => handleTransition("approved")}>
              Approve
            </Button>
          )}
          {allowedNext.includes("rejected") && (
            <Button
              variant="neutral-primary"
              size="sm"
              disabled={isSubmitting}
              onClick={() => handleTransition("rejected")}
              className="text-red-600 hover:text-red-700"
            >
              Reject
            </Button>
          )}
          {allowedNext.includes("draft") && version.status !== "draft" && (
            <Button
              variant="neutral-primary"
              size="sm"
              disabled={isSubmitting}
              onClick={() => handleTransition("draft")}
            >
              Return to Draft
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
