/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { DollarSign } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Loader } from "@plane/ui";
import { formatUsd, parseUsd } from "@/components/agent-infra/catalog-utils";
import { useModelRouting } from "@/hooks/use-catalog";

type TBudgetPanelProps = {
  workspaceSlug: string;
  projectId: string;
};

export function BudgetPanel(props: TBudgetPanelProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { configs, isLoading, error } = useModelRouting(workspaceSlug, projectId);

  const budgetRows = useMemo(() => {
    return (configs ?? []).map((config) => {
      const limit = parseUsd(config.budget_limit_usd);
      const used = parseUsd(config.budget_used_usd);
      const utilization = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
      return { config, limit, used, utilization };
    });
  }, [configs]);

  if (error) {
    return (
      <div className="rounded-lg border border-subtle bg-surface-1 px-4 py-6 text-center text-13 text-tertiary">
        {t("agent_infra.error_state.description")}
      </div>
    );
  }

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
        <DollarSign className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.models.budget_panel")}</h3>
      </div>

      {budgetRows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.models.budget_empty")}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {budgetRows.map(({ config, limit, used, utilization }) => (
            <div key={config.id} className="rounded-lg border border-subtle bg-surface-1 p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-13 font-semibold text-primary">{config.model_ref}</p>
                <span className="text-11 capitalize text-tertiary">{config.budget_period}</span>
              </div>
              <p className="mt-2 text-12 text-secondary">
                {formatUsd(used)} / {formatUsd(limit)}
              </p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-layer-2">
                <div
                  className={`h-full rounded-full ${utilization >= 90 ? "bg-red-500" : utilization >= 70 ? "bg-amber-500" : "bg-green-500"}`}
                  style={{ width: `${utilization}%` }}
                />
              </div>
              <p className="mt-2 text-11 text-tertiary">
                {t("agent_infra.models.utilization", { percent: utilization })}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
