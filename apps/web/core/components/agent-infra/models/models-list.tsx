/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Cpu } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import {
  CATALOG_STATUS_BADGE_CLASSES,
  formatCost,
  truncateContentHash,
} from "../catalog-utils";
import type { ModelEntry } from "../workforce/workforce-types";

type TModelsListProps = {
  models?: ModelEntry[];
  isLoading?: boolean;
};

const EMPTY_MODELS: ModelEntry[] = [];

export function ModelsList(props: TModelsListProps) {
  const { models = EMPTY_MODELS, isLoading = false } = props;
  const { t } = useTranslation();

  const sortedModels = useMemo(
    () =>
      [...models].sort((left, right) => {
        const leftPriority = left.routing_priority ?? Number.MAX_SAFE_INTEGER;
        const rightPriority = right.routing_priority ?? Number.MAX_SAFE_INTEGER;
        if (leftPriority !== rightPriority) return leftPriority - rightPriority;
        return (left.name ?? left.path).localeCompare(right.name ?? right.path);
      }),
    [models]
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
        <Cpu className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.models_tab.title")}</h3>
      </div>

      {sortedModels.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <p className="text-14 font-semibold text-primary">{t("agent_infra.models_tab.empty")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>{t("agent_infra.models_tab.provider")}</TableHead>
                <TableHead>{t("agent_infra.models_tab.capabilities")}</TableHead>
                <TableHead>{t("agent_infra.models_tab.cost")}</TableHead>
                <TableHead>{t("agent_infra.models_tab.routing_priority")}</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedModels.map((model) => {
                const hasValidationErrors = (model.validation_errors?.length ?? 0) > 0;
                const costLabel =
                  model.cost_per_1k_input !== undefined || model.cost_per_1k_output !== undefined
                    ? `${formatCost(model.cost_per_1k_input)} / ${formatCost(model.cost_per_1k_output)}`
                    : "—";

                return (
                  <TableRow key={model.path}>
                    <TableCell className="text-13 font-medium text-primary">{model.name ?? model.path}</TableCell>
                    <TableCell className="text-13 text-secondary">{model.provider ?? "—"}</TableCell>
                    <TableCell className="max-w-xs truncate text-13 text-secondary">
                      {(model.capabilities ?? []).join(", ") || "—"}
                    </TableCell>
                    <TableCell className="text-13 text-secondary">{costLabel}</TableCell>
                    <TableCell className="text-13 text-secondary">{model.routing_priority ?? "—"}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span
                          className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[model.status]}`}
                        >
                          {model.status}
                        </span>
                        {model.shadow_mode && (
                          <Badge variant="outline-neutral" size="sm" disabled>
                            {t("agent_infra.models_tab.shadow_mode")}
                          </Badge>
                        )}
                        {hasValidationErrors && (
                          <Badge variant="accent-warning" size="sm" disabled>
                            {model.validation_errors?.length} warning
                            {(model.validation_errors?.length ?? 0) === 1 ? "" : "s"}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-12 text-tertiary">
                      {truncateContentHash(model.content_hash)}
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
