/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { CheckCircle2, History, ShieldAlert, XCircle } from "lucide-react";
import { Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { usePolicyDecisions } from "@/hooks/use-agent-infra";
import type { TDecisionOutcome, TPolicyDecision } from "../governance-types";

type TDecisionHistoryProps = {
  workspaceSlug: string;
  projectId: string;
};

const OUTCOME_ICONS: Record<TDecisionOutcome, { icon: typeof CheckCircle2; color: string }> = {
  allow: { icon: CheckCircle2, color: "text-emerald-600" },
  deny: { icon: XCircle, color: "text-red-600" },
  require_approval: { icon: ShieldAlert, color: "text-amber-600" },
};

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function DecisionHistory(props: TDecisionHistoryProps) {
  const { workspaceSlug, projectId } = props;
  const { decisions, isLoading, error } = usePolicyDecisions(workspaceSlug, projectId);

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="40px" />
        <Loader.Item height="200px" />
      </Loader>
    );
  }

  if (error) {
    return (
      <div className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/30 rounded-md border px-4 py-3 text-13">
        Failed to load decision history.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <History className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">Policy Decision History</h3>
        <span className="text-12 text-tertiary">({decisions?.length ?? 0})</span>
      </div>

      {!decisions || decisions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <History className="mx-auto mb-3 h-10 w-10 text-tertiary" />
          <p className="text-14 font-semibold text-primary">No decisions recorded</p>
          <p className="mt-1 text-13 text-tertiary">
            Policy decisions will appear here as agents request authorization.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Outcome</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Evaluated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(decisions as TPolicyDecision[]).map((decision) => {
                const outcomeConf = OUTCOME_ICONS[decision.outcome];
                const Icon = outcomeConf?.icon ?? XCircle;
                return (
                  <TableRow key={decision.id}>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <Icon className={`h-4 w-4 ${outcomeConf?.color ?? "text-tertiary"}`} />
                        <span className="text-13 font-medium capitalize">{decision.outcome.replace("_", " ")}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-13 text-secondary">
                      <span className="font-mono text-12">
                        {decision.subject_type}:{decision.subject_ref}
                      </span>
                    </TableCell>
                    <TableCell className="text-13 text-secondary">{decision.action}</TableCell>
                    <TableCell className="text-13 text-secondary">
                      <span className="font-mono text-12">
                        {decision.resource_type}:{decision.resource_ref}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-12 text-tertiary">{decision.reason}</TableCell>
                    <TableCell className="text-12 text-tertiary">{formatDate(decision.evaluated_at)}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
