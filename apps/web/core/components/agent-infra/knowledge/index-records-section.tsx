/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Database, RefreshCw } from "lucide-react";
import { Badge } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import type { TIndexRequestStatus, TKnowledgeIndexRecord } from "./knowledge-types";
import { formatDateTime } from "./knowledge-utils";

type TIndexRecordsSectionProps = {
  records: TKnowledgeIndexRecord[];
  isLoading?: boolean;
};

const STATUS_VARIANT: Record<TIndexRequestStatus, string> = {
  pending: "outline-neutral",
  acknowledged: "accent-primary",
  in_progress: "accent-warning",
  completed: "accent-success",
  failed: "accent-destructive",
};

export function IndexRecordsSection(props: TIndexRecordsSectionProps) {
  const { records, isLoading = false } = props;

  const stats = useMemo(() => {
    const pending = records.filter((r) => r.status === "pending").length;
    const inProgress = records.filter((r) => r.status === "in_progress" || r.status === "acknowledged").length;
    const completed = records.filter((r) => r.status === "completed").length;
    const failed = records.filter((r) => r.status === "failed").length;
    return { pending, inProgress, completed, failed };
  }, [records]);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-10 rounded-lg bg-surface-2" />
        <div className="h-40 rounded-lg bg-surface-2" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-tertiary" />
          <h4 className="text-14 font-semibold text-primary">Index Reconciliation</h4>
        </div>
        <div className="flex items-center gap-3 text-12 text-tertiary">
          <span>{stats.pending} pending</span>
          <span>{stats.inProgress} in progress</span>
          <span className="text-green-600">{stats.completed} completed</span>
          {stats.failed > 0 && <span className="text-red-600">{stats.failed} failed</span>}
        </div>
      </div>

      {records.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center">
          <RefreshCw className="mx-auto h-8 w-8 text-tertiary" />
          <p className="mt-2 text-14 font-medium text-primary">No index records</p>
          <p className="mt-1 text-12 text-tertiary">
            Index records will appear when knowledge is synced to external systems
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Version</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Requested</TableHead>
                <TableHead>Retries</TableHead>
                <TableHead>Verified</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((record) => (
                <TableRow key={record.id}>
                  <TableCell className="font-mono text-12 text-secondary">
                    {record.knowledge_version.slice(0, 8)}…
                  </TableCell>
                  <TableCell className="capitalize text-13 text-secondary">
                    {record.action}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[record.status] as any} size="sm" disabled>
                      {record.status.replace("_", " ")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-12 text-tertiary">
                    {formatDateTime(record.requested_at)}
                  </TableCell>
                  <TableCell className="text-12 text-secondary">
                    {record.retry_count}/{record.max_retries}
                  </TableCell>
                  <TableCell>
                    {record.is_verified ? (
                      <span className="text-green-600 text-12">✓</span>
                    ) : (
                      <span className="text-tertiary text-12">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {stats.failed > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-900 dark:bg-red-950/20">
          <p className="text-12 font-medium text-red-800 dark:text-red-300">
            {stats.failed} index operation{stats.failed === 1 ? "" : "s"} failed
          </p>
          {records
            .filter((r) => r.status === "failed" && r.failure_reason)
            .slice(0, 3)
            .map((r) => (
              <p key={r.id} className="mt-1 text-11 text-red-700 dark:text-red-400">
                • {r.failure_reason}
              </p>
            ))}
        </div>
      )}
    </div>
  );
}
