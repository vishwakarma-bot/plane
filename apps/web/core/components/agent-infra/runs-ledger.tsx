/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Bot, Inbox } from "lucide-react";
import type { TBadgeVariant } from "@plane/ui";
import { Badge, Button, Loader } from "@plane/ui";
import { useAgentRunLedger } from "@/hooks/use-agent-infra";
import type { TProgressionOutcome, TRunLedgerItem, TRunOutcome } from "./mock-data";
import {
  DISPOSITION_STATUS_LABELS,
  PROGRESSION_OUTCOME_LABELS,
  RUN_OUTCOME_LABELS,
  formatCost,
  formatRelativeTime,
} from "./mock-data";
import { ReviewBadge } from "./review-badge";

type TRunsLedgerProps = {
  workspaceSlug: string;
  projectId: string;
  onSelectRun?: (runId: string) => void;
};

const OUTCOME_VARIANTS: Record<TRunOutcome, TBadgeVariant> = {
  success: "accent-success",
  failed: "accent-destructive",
  partial: "accent-warning",
};

const PROGRESSION_VARIANTS: Record<TProgressionOutcome, TBadgeVariant> = {
  auto_progress: "accent-success",
  awaiting_disposition: "accent-warning",
  blocked: "accent-destructive",
};

const DISPOSITION_VARIANTS: Record<string, TBadgeVariant> = {
  pending: "accent-warning",
  approved: "accent-success",
  rejected: "accent-destructive",
  rework: "accent-warning",
};

export function RunsLedger(props: TRunsLedgerProps) {
  const { workspaceSlug, projectId, onSelectRun } = props;
  const [outcomeFilter, setOutcomeFilter] = useState<string>("");
  const [progressionFilter, setProgressionFilter] = useState<string>("");
  const [agentRefFilter, setAgentRefFilter] = useState("");
  const [cursor, setCursor] = useState<string | undefined>();
  const [displayRuns, setDisplayRuns] = useState<TRunLedgerItem[]>([]);

  const { runs, isLoading, error, nextCursor } = useAgentRunLedger(workspaceSlug, projectId, {
    outcome: outcomeFilter || undefined,
    progression_outcome: progressionFilter || undefined,
    agent_ref: agentRefFilter.trim() || undefined,
    cursor,
    per_page: 25,
  });

  useEffect(() => {
    if (!runs) return;
    if (!cursor) {
      setDisplayRuns(runs);
      return;
    }
    setDisplayRuns((previous) => {
      const existingIds = new Set(previous.map((run) => run.id));
      return [...previous, ...runs.filter((run) => !existingIds.has(run.id))];
    });
  }, [runs, cursor]);

  const handleFilterChange = () => {
    setCursor(undefined);
    setDisplayRuns([]);
  };

  if (isLoading && !runs) {
    return (
      <div className="flex flex-col gap-3">
        <Loader className="space-y-3">
          <Loader.Item height="40px" />
          <Loader.Item height="48px" />
          <Loader.Item height="48px" />
          <Loader.Item height="48px" />
        </Loader>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-subtle bg-surface-1 px-6 py-12 text-center">
        <p className="text-14 font-semibold text-primary">Unable to load runs</p>
        <p className="mt-1 text-13 text-tertiary">Something went wrong while loading the run ledger.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-14 font-semibold text-primary">Runs</h3>
        <p className="text-11 text-tertiary">Project-wide agent run history with authority layer status.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-subtle bg-surface-1 p-3">
        <FilterField label="Outcome">
          <select
            value={outcomeFilter}
            onChange={(event) => {
              setOutcomeFilter(event.target.value);
              handleFilterChange();
            }}
            className="w-full rounded-md border border-subtle bg-layer-2 px-2 py-1.5 text-13 text-primary"
          >
            <option value="">All outcomes</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="partial">Partial</option>
          </select>
        </FilterField>

        <FilterField label="Progression">
          <select
            value={progressionFilter}
            onChange={(event) => {
              setProgressionFilter(event.target.value);
              handleFilterChange();
            }}
            className="w-full rounded-md border border-subtle bg-layer-2 px-2 py-1.5 text-13 text-primary"
          >
            <option value="">All progression</option>
            <option value="auto_progress">Auto Progress</option>
            <option value="awaiting_disposition">Awaiting Disposition</option>
            <option value="blocked">Blocked</option>
          </select>
        </FilterField>

        <FilterField label="Agent ref" className="min-w-45 flex-1">
          <input
            type="text"
            value={agentRefFilter}
            onChange={(event) => setAgentRefFilter(event.target.value)}
            onBlur={handleFilterChange}
            onKeyDown={(event) => {
              if (event.key === "Enter") handleFilterChange();
            }}
            placeholder="Filter by agent ref"
            className="w-full rounded-md border border-subtle bg-layer-2 px-2 py-1.5 text-13 text-primary placeholder:text-placeholder"
          />
        </FilterField>
      </div>

      {!displayRuns || displayRuns.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-16 text-center">
          <Inbox className="h-10 w-10 text-tertiary" />
          <div>
            <p className="text-14 font-semibold text-primary">No runs found</p>
            <p className="mt-1 max-w-sm text-13 text-tertiary">Adjust filters or wait for agent runs to complete.</p>
          </div>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <div className="hidden grid-cols-[1.2fr_1fr_auto_auto_auto_auto_auto] gap-3 border-b border-subtle bg-layer-2 px-3 py-2 text-11 font-medium text-tertiary lg:grid">
            <span>Agent</span>
            <span>Model</span>
            <span>Outcome</span>
            <span>Progression</span>
            <span>Verdict</span>
            <span>Disposition</span>
            <span>Started / Cost</span>
          </div>

          <div className="divide-y divide-subtle">
            {displayRuns.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => onSelectRun?.(run.id)}
                className="flex w-full flex-col gap-2 px-3 py-3 text-left transition-colors hover:bg-layer-1 lg:grid lg:grid-cols-[1.2fr_1fr_auto_auto_auto_auto_auto] lg:items-center lg:gap-3"
              >
                <div className="flex items-center gap-2">
                  <Bot className="h-3.5 w-3.5 text-tertiary" />
                  <span className="truncate text-13 font-medium text-primary">{run.agentRef}</span>
                </div>
                <span className="truncate text-13 text-secondary">{run.modelUsed}</span>
                <Badge variant={OUTCOME_VARIANTS[run.outcome]} size="sm" disabled>
                  {RUN_OUTCOME_LABELS[run.outcome]}
                </Badge>
                {run.progressionOutcome ? (
                  <Badge variant={PROGRESSION_VARIANTS[run.progressionOutcome]} size="sm" disabled>
                    {PROGRESSION_OUTCOME_LABELS[run.progressionOutcome]}
                  </Badge>
                ) : (
                  <span className="text-11 text-placeholder">—</span>
                )}
                {run.verdict ? (
                  <ReviewBadge verdict={run.verdict} />
                ) : (
                  <span className="text-11 text-placeholder">—</span>
                )}
                {run.disposition ? (
                  <Badge variant={DISPOSITION_VARIANTS[run.disposition] ?? "outline-neutral"} size="sm" disabled>
                    {DISPOSITION_STATUS_LABELS[run.disposition]}
                  </Badge>
                ) : (
                  <span className="text-11 text-placeholder">—</span>
                )}
                <div className="flex flex-col">
                  <span className="text-11 text-secondary">{formatRelativeTime(run.startedAt)}</span>
                  <span className="text-11 text-tertiary">{formatCost(run.costUsd)}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {nextCursor && (
        <div className="flex justify-center">
          <Button variant="outline-primary" size="sm" onClick={() => setCursor(nextCursor)} disabled={isLoading}>
            {isLoading ? "Loading…" : "Load more"}
          </Button>
        </div>
      )}
    </div>
  );
}

function FilterField(props: { label: string; children: ReactNode; className?: string }) {
  const { label, children, className = "" } = props;

  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      <span className="text-11 font-medium text-tertiary">{label}</span>
      {children}
    </label>
  );
}
