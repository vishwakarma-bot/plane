/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { AlertOctagon, CheckCircle2, Clock } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Badge } from "@plane/ui";
import type { TConflictStatus, TKnowledgeConflictRecord } from "./knowledge-types";

type TConflictResolutionPanelProps = {
  conflicts: TKnowledgeConflictRecord[];
  isLoading?: boolean;
  onResolve: (
    conflictId: string,
    data: { status: string; resolution_summary: string; winning_version?: string }
  ) => Promise<void>;
};

const STATUS_BADGES: Record<TConflictStatus, { label: string; variant: string; icon: React.ElementType }> = {
  open: { label: "Open", variant: "accent-destructive", icon: AlertOctagon },
  acknowledged: { label: "Acknowledged", variant: "accent-warning", icon: Clock },
  resolved: { label: "Resolved", variant: "accent-success", icon: CheckCircle2 },
  superseded: { label: "Superseded", variant: "outline-neutral", icon: Clock },
};

const CONFLICT_TYPE_LABELS: Record<string, string> = {
  authority: "Authority Conflict",
  semantic: "Semantic Conflict",
  staleness: "Staleness Conflict",
};

function ConflictCard(props: {
  conflict: TKnowledgeConflictRecord;
  onResolve: TConflictResolutionPanelProps["onResolve"];
}) {
  const { conflict, onResolve } = props;
  const [showForm, setShowForm] = useState(false);
  const [resolution, setResolution] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const badge = STATUS_BADGES[conflict.status];
  const Icon = badge.icon;

  const handleResolve = useCallback(async () => {
    if (!resolution.trim()) return;
    setIsSubmitting(true);
    try {
      await onResolve(conflict.id, { status: "resolved", resolution_summary: resolution });
      setShowForm(false);
      setResolution("");
    } finally {
      setIsSubmitting(false);
    }
  }, [conflict.id, onResolve, resolution]);

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-tertiary" />
            <span className="text-13 font-medium text-primary">
              {CONFLICT_TYPE_LABELS[conflict.conflict_type] ?? conflict.conflict_type}
            </span>
            <Badge variant={badge.variant as any} size="sm" disabled>
              {badge.label}
            </Badge>
            {conflict.blocks_execution && (
              <span className="bg-red-100 text-red-800 dark:bg-red-950/40 dark:text-red-300 rounded-sm px-1.5 py-0.5 text-10 font-medium">
                Blocks Execution
              </span>
            )}
          </div>
          {conflict.description && <p className="mt-2 text-12 text-secondary">{conflict.description}</p>}
          <p className="text-quaternary mt-1 text-11">
            Version A: {conflict.version_a.slice(0, 8)}… vs Version B: {conflict.version_b.slice(0, 8)}…
          </p>
          {conflict.resolution_summary && (
            <p className="mt-2 text-12 text-tertiary italic">Resolution: {conflict.resolution_summary}</p>
          )}
        </div>

        {conflict.status === "open" && !showForm && (
          <Button variant="primary" size="sm" onClick={() => setShowForm(true)}>
            Resolve
          </Button>
        )}
      </div>

      {showForm && (
        <div className="mt-4 flex flex-col gap-3 rounded-md border border-subtle bg-surface-2 p-3">
          <label htmlFor="conflict-resolution" className="text-12 font-medium text-secondary">
            How was this conflict resolved?
          </label>
          <textarea
            id="conflict-resolution"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            className="placeholder:text-quaternary focus:border-accent-primary min-h-[80px] rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary focus:outline-none"
            placeholder="Describe the resolution decision..."
          />
          <div className="flex items-center justify-end gap-2">
            <Button variant="neutral-primary" size="sm" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" disabled={isSubmitting || !resolution.trim()} onClick={handleResolve}>
              {isSubmitting ? "Resolving..." : "Mark Resolved"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ConflictResolutionPanel(props: TConflictResolutionPanelProps) {
  const { conflicts, isLoading = false, onResolve } = props;
  const { t } = useTranslation();

  const openConflicts = conflicts.filter((c) => c.status === "open" || c.status === "acknowledged");
  const resolvedConflicts = conflicts.filter((c) => c.status === "resolved" || c.status === "superseded");

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-12 rounded-lg bg-surface-2" />
        <div className="h-12 rounded-lg bg-surface-2" />
      </div>
    );
  }

  if (conflicts.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center">
        <CheckCircle2 className="text-green-500 mx-auto h-8 w-8" />
        <p className="mt-2 text-14 font-medium text-primary">No conflicts detected</p>
        <p className="mt-1 text-12 text-tertiary">All knowledge sources are consistent</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h4 className="text-14 font-semibold text-primary">Knowledge Conflicts</h4>
        <span className="text-12 text-tertiary">
          {openConflicts.length} open · {resolvedConflicts.length} resolved
        </span>
      </div>

      {openConflicts.length > 0 && (
        <div className="flex flex-col gap-3">
          {openConflicts.map((conflict) => (
            <ConflictCard key={conflict.id} conflict={conflict} onResolve={onResolve} />
          ))}
        </div>
      )}

      {resolvedConflicts.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-12 font-medium text-tertiary hover:text-secondary">
            Show {resolvedConflicts.length} resolved conflict{resolvedConflicts.length === 1 ? "" : "s"}
          </summary>
          <div className="mt-3 flex flex-col gap-3 opacity-70">
            {resolvedConflicts.map((conflict) => (
              <ConflictCard key={conflict.id} conflict={conflict} onResolve={onResolve} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
