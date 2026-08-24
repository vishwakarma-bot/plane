/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { GitFork } from "lucide-react";
import { Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { useSoDConstraints } from "@/hooks/use-agent-infra";
import type { TSeparationOfDutyConstraint } from "../governance-types";

type TSoDConstraintsListProps = {
  workspaceSlug: string;
  projectId: string;
};

export function SoDConstraintsList(props: TSoDConstraintsListProps) {
  const { workspaceSlug, projectId } = props;
  const { constraints, isLoading, error } = useSoDConstraints(workspaceSlug, projectId);

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="40px" />
        <Loader.Item height="160px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <GitFork className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">Separation of Duty Constraints</h3>
        <span className="text-12 text-tertiary">({constraints?.length ?? 0})</span>
      </div>

      {error && (
        <div className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/30 rounded-md border px-4 py-3 text-13">
          Failed to load SoD constraints.
        </div>
      )}

      {!error && (!constraints || constraints.length === 0) ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <GitFork className="mx-auto mb-3 h-10 w-10 text-tertiary" />
          <p className="text-14 font-semibold text-primary">No constraints active</p>
          <p className="mt-1 text-13 text-tertiary">
            Separation-of-duty constraints are automatically created when policies with SoD rules are approved.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Conflicting Actions</TableHead>
                <TableHead>Scope</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(constraints as TSeparationOfDutyConstraint[]).map((constraint) => (
                <TableRow key={constraint.id}>
                  <TableCell className="text-13 font-medium text-primary">{constraint.name}</TableCell>
                  <TableCell className="max-w-xs text-13 text-secondary">{constraint.description}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {constraint.conflicting_actions.map((action) => (
                        <span key={action} className="rounded-sm bg-layer-2 px-2 py-0.5 text-12 text-secondary">
                          {action}
                        </span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-13 text-secondary capitalize">{constraint.scope}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
