/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { CheckCircle2, Inbox, ShieldCheck, XCircle } from "lucide-react";
import { Loader } from "@plane/ui";
import { useActionApprovals } from "@/hooks/use-agent-infra";
import agentInfraService from "@/services/agent-infra.service";
import type { TActionApproval, TApprovalStatus } from "../governance-types";

type TApprovalQueueProps = {
  workspaceSlug: string;
  projectId: string;
};

const STATUS_CONFIG: Record<TApprovalStatus, { label: string; classes: string }> = {
  pending: { label: "Pending", classes: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300" },
  approved: {
    label: "Approved",
    classes: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300",
  },
  rejected: { label: "Rejected", classes: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" },
  expired: { label: "Expired", classes: "bg-layer-2 text-tertiary" },
  cancelled: { label: "Cancelled", classes: "bg-layer-2 text-tertiary" },
};

const RISK_COLORS: Record<string, string> = {
  low: "text-emerald-600",
  medium: "text-amber-600",
  high: "text-red-600",
  critical: "text-red-700 font-semibold",
};

const FILTER_TABS = ["pending", "approved", "rejected", "expired"] as const;

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
}

export function ApprovalQueue(props: TApprovalQueueProps) {
  const { workspaceSlug, projectId } = props;
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const { approvals, isLoading, error, mutate } = useActionApprovals(
    workspaceSlug,
    projectId,
    statusFilter ? { status: statusFilter } : undefined
  );
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const handleReview = async (approvalId: string, status: "approved" | "rejected") => {
    setActionLoading(true);
    try {
      await agentInfraService.reviewApproval(workspaceSlug, projectId, approvalId, {
        status,
        reason: reviewReason || undefined,
      });
      await mutate();
      setReviewingId(null);
      setReviewReason("");
    } catch {
      // handled by SWR
    } finally {
      setActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="96px" />
        <Loader.Item height="96px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-tertiary" />
        <div>
          <h3 className="text-14 font-semibold text-primary">Action Approval Queue</h3>
          <p className="text-11 text-tertiary">Exact-action approvals requiring human review before execution.</p>
        </div>
      </div>

      <div className="inline-flex gap-1 self-start rounded-lg bg-surface-1 p-1">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setStatusFilter(tab)}
            className={`rounded-md px-3 py-1.5 text-13 font-medium capitalize transition-colors ${
              statusFilter === tab ? "bg-layer-2 text-primary" : "text-tertiary hover:bg-layer-1 hover:text-secondary"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {error && (
        <div className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/30 rounded-md border px-4 py-3 text-13">
          Failed to load approvals.
        </div>
      )}

      {!error && (!approvals || approvals.length === 0) ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-16 text-center">
          <Inbox className="h-10 w-10 text-tertiary" />
          <div>
            <p className="text-14 font-semibold text-primary">No {statusFilter} approvals</p>
            <p className="mt-1 max-w-sm text-13 text-tertiary">
              Actions requiring human approval will appear here when triggered by require_approval policies.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {(approvals ?? []).map((approval) => {
            const a = approval as TActionApproval;
            const statusConf = STATUS_CONFIG[a.status];
            const isReviewing = reviewingId === a.id;
            return (
              <div key={a.id} className="rounded-lg border border-subtle bg-surface-1 p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium ${statusConf.classes}`}
                      >
                        {statusConf.label}
                      </span>
                      <span className={`text-12 font-medium ${RISK_COLORS[a.risk_level] ?? "text-secondary"}`}>
                        {a.risk_level} risk
                      </span>
                      {a.is_expired && (
                        <span className="rounded-sm bg-layer-2 px-1.5 py-0.5 text-11 text-tertiary">Expired</span>
                      )}
                    </div>
                    <div className="text-13 text-primary">
                      <span className="font-medium">
                        {a.subject_type}:{a.subject_ref}
                      </span>
                      <span className="text-tertiary"> wants to </span>
                      <span className="font-medium">{a.action}</span>
                      <span className="text-tertiary"> on </span>
                      <span className="font-medium">
                        {a.target_type}:{a.target_ref}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-3 text-11 text-tertiary">
                      <span>
                        Digest: <span className="font-mono">{a.target_digest?.slice(0, 12)}…</span>
                      </span>
                      {a.expires_at && <span>Expires: {formatDate(a.expires_at)}</span>}
                      <span>Requested: {formatDate(a.created_at)}</span>
                    </div>
                    {a.review_reason && (
                      <p className="rounded-md bg-layer-2 px-3 py-2 text-12 text-secondary">{a.review_reason}</p>
                    )}
                  </div>

                  {a.status === "pending" && !a.is_expired && (
                    <div className="shrink-0 lg:w-56">
                      {isReviewing ? (
                        <div className="space-y-2">
                          <label htmlFor={`review-reason-${a.id}`} className="text-12 font-medium text-secondary">
                            Review reason
                          </label>
                          <input
                            id={`review-reason-${a.id}`}
                            type="text"
                            value={reviewReason}
                            onChange={(e) => setReviewReason(e.target.value)}
                            placeholder="Reason (optional)"
                            className="w-full rounded-md border border-subtle bg-surface-1 px-3 py-1.5 text-12"
                          />
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={actionLoading}
                              onClick={() => handleReview(a.id, "approved")}
                              className="bg-emerald-600 hover:bg-emerald-700 flex-1 rounded-md px-2 py-1.5 text-12 font-medium text-white disabled:opacity-50"
                            >
                              <CheckCircle2 className="mr-1 inline h-3.5 w-3.5" />
                              Approve
                            </button>
                            <button
                              type="button"
                              disabled={actionLoading}
                              onClick={() => handleReview(a.id, "rejected")}
                              className="bg-red-600 hover:bg-red-700 flex-1 rounded-md px-2 py-1.5 text-12 font-medium text-white disabled:opacity-50"
                            >
                              <XCircle className="mr-1 inline h-3.5 w-3.5" />
                              Reject
                            </button>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setReviewingId(null);
                              setReviewReason("");
                            }}
                            className="w-full rounded-md border border-subtle px-2 py-1 text-11 text-tertiary hover:bg-layer-1"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setReviewingId(a.id)}
                          className="w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 font-medium text-primary hover:bg-layer-1"
                        >
                          Review
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
