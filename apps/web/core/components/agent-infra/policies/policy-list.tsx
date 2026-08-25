/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Shield, ShieldAlert } from "lucide-react";
import { Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import type { TAuthorizationPolicyListItem } from "../governance-types";
import { EFFECT_LABELS, POLICY_EFFECT_BADGE, POLICY_STATUS_BADGE, STATUS_LABELS } from "./policy-types";

type TPolicyListProps = {
  policies?: TAuthorizationPolicyListItem[];
  isLoading?: boolean;
  selectedId?: string | null;
  onPolicySelect?: (id: string) => void;
};

const EMPTY_POLICIES: TAuthorizationPolicyListItem[] = [];

export function PolicyList(props: TPolicyListProps) {
  const { policies = EMPTY_POLICIES, isLoading = false, selectedId, onPolicySelect } = props;

  const sortedPolicies = useMemo(() => [...policies].toSorted((a, b) => a.priority - b.priority), [policies]);

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="40px" />
        <Loader.Item height="240px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-tertiary" />
          <h3 className="text-14 font-semibold text-primary">Authorization Policies</h3>
          <span className="text-12 text-tertiary">({policies.length})</span>
        </div>
      </div>

      {sortedPolicies.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <Shield className="mx-auto mb-3 h-10 w-10 text-tertiary" />
          <p className="text-14 font-semibold text-primary">No policies defined</p>
          <p className="mt-1 text-13 text-tertiary">
            Authorization policies control what agents can do in this project.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Priority</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Effect</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Classification</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Rev</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedPolicies.map((policy) => {
                const isSelected = selectedId === policy.id;
                return (
                  <TableRow key={policy.id}>
                    <TableCell className="font-mono w-16 text-center text-13 text-secondary">
                      {policy.priority}
                    </TableCell>
                    <TableCell>
                      <button
                        type="button"
                        className={`text-left text-13 font-medium hover:text-accent-primary ${isSelected ? "text-accent-primary" : "text-primary"}`}
                        onClick={() => onPolicySelect?.(policy.id)}
                      >
                        <div className="flex items-center gap-1.5">
                          {policy.emergency && <ShieldAlert className="text-red-500 h-3.5 w-3.5" />}
                          {policy.name}
                        </div>
                        <span className="text-11 text-tertiary">v{policy.version}</span>
                      </button>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium ${POLICY_EFFECT_BADGE[policy.effect]}`}
                      >
                        {EFFECT_LABELS[policy.effect]}
                      </span>
                    </TableCell>
                    <TableCell className="text-13 text-secondary capitalize">{policy.scope}</TableCell>
                    <TableCell className="text-13 text-secondary capitalize">
                      {policy.autonomy_classification}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium ${POLICY_STATUS_BADGE[policy.status]}`}
                      >
                        {STATUS_LABELS[policy.status]}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-12 text-tertiary">#{policy.revision_number}</TableCell>
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
