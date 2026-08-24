/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import { Route } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import type { TModelRoutingConfig } from "@/components/agent-infra/governance-types";
import { useModelRouting } from "@/hooks/use-catalog";
import catalogService from "@/services/catalog.service";

type TRoutingPanelProps = {
  workspaceSlug: string;
  projectId: string;
};

const EMPTY_CONFIGS: TModelRoutingConfig[] = [];

export function RoutingPanel(props: TRoutingPanelProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { configs, isLoading, error, mutate } = useModelRouting(workspaceSlug, projectId);
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const sortedConfigs = useMemo(() => {
    const list = configs ?? EMPTY_CONFIGS;
    return [...list].toSorted((a: TModelRoutingConfig, b: TModelRoutingConfig) => a.routing_priority - b.routing_priority);
  }, [configs]);

  const handleUpdate = useCallback(
    async (config: TModelRoutingConfig, patch: Partial<TModelRoutingConfig>) => {
      setSubmittingId(config.id);
      try {
        await catalogService.updateModelRouting(workspaceSlug, projectId, config.id, patch);
        await mutate();
      } finally {
        setSubmittingId(null);
      }
    },
    [mutate, projectId, workspaceSlug]
  );

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
        <Loader.Item height="200px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Route className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.models.routing_panel")}</h3>
      </div>

      {sortedConfigs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.models.routing_empty")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("agent_infra.models.model")}</TableHead>
                <TableHead>{t("agent_infra.models_tab.routing_priority")}</TableHead>
                <TableHead>{t("agent_infra.models_tab.shadow_mode")}</TableHead>
                <TableHead>{t("agent_infra.models.enabled")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedConfigs.map((config) => (
                <TableRow key={config.id}>
                  <TableCell className="text-13 font-medium text-primary">{config.model_ref}</TableCell>
                  <TableCell className="text-13 text-secondary">{config.routing_priority}</TableCell>
                  <TableCell>
                    <label className="inline-flex items-center gap-2 text-13">
                      <input
                        type="checkbox"
                        checked={config.shadow_mode}
                        disabled={submittingId === config.id}
                        onChange={(event) => handleUpdate(config, { shadow_mode: event.target.checked })}
                      />
                      {config.shadow_mode ? t("agent_infra.models.yes") : t("agent_infra.models.no")}
                    </label>
                  </TableCell>
                  <TableCell>
                    <label className="inline-flex items-center gap-2 text-13">
                      <input
                        type="checkbox"
                        checked={config.enabled}
                        disabled={submittingId === config.id}
                        onChange={(event) => handleUpdate(config, { enabled: event.target.checked })}
                      />
                      {config.enabled ? t("agent_infra.models.enabled_yes") : t("agent_infra.models.enabled_no")}
                    </label>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
