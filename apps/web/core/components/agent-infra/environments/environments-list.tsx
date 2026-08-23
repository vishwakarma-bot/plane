/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Server } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { CATALOG_STATUS_BADGE_CLASSES, truncateContentHash } from "../catalog-utils";
import type { EnvironmentEntry } from "../workforce/workforce-types";

type TEnvironmentsListProps = {
  environments?: EnvironmentEntry[];
  isLoading?: boolean;
  selectedPath?: string | null;
  onEnvironmentSelect?: (path: string) => void;
};

const EMPTY_ENVIRONMENTS: EnvironmentEntry[] = [];

export function EnvironmentsList(props: TEnvironmentsListProps) {
  const { environments = EMPTY_ENVIRONMENTS, isLoading = false, selectedPath, onEnvironmentSelect } = props;
  const { t } = useTranslation();

  const sortedEnvironments = useMemo(
    () =>
      environments.toSorted((left, right) =>
        (left.name ?? left.path).localeCompare(right.name ?? right.path)
      ),
    [environments]
  );

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
      <div className="flex items-center gap-2">
        <Server className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.environments_tab.title")}</h3>
      </div>

      {sortedEnvironments.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <p className="text-14 font-semibold text-primary">{t("agent_infra.environments_tab.empty")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>{t("agent_infra.environments_tab.toolchain")}</TableHead>
                <TableHead>{t("agent_infra.environments_tab.capabilities")}</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedEnvironments.map((environment) => {
                const isSelected = selectedPath === environment.path;
                const hasValidationErrors = (environment.validation_errors?.length ?? 0) > 0;

                return (
                  <TableRow key={environment.path}>
                    <TableCell>
                      <button
                        type="button"
                        className={`text-left text-13 font-medium hover:text-accent-primary ${
                          isSelected ? "text-accent-primary" : "text-primary"
                        }`}
                        onClick={() => onEnvironmentSelect?.(environment.path)}
                      >
                        {environment.name ?? environment.path}
                      </button>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-13 text-secondary">
                      {(environment.toolchain ?? []).join(", ") || "—"}
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-13 text-secondary">
                      {(environment.capabilities ?? []).join(", ") || "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span
                          className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[environment.status]}`}
                        >
                          {environment.status}
                        </span>
                        {hasValidationErrors && (
                          <Badge variant="accent-warning" size="sm" disabled>
                            {environment.validation_errors?.length} warning
                            {(environment.validation_errors?.length ?? 0) === 1 ? "" : "s"}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-12 text-tertiary">
                      {truncateContentHash(environment.content_hash)}
                    </TableCell>
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
