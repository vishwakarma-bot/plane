/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { ArrowDown } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { CATALOG_STATUS_BADGE_CLASSES } from "../catalog-utils";
import type { ModelEntry } from "../workforce/workforce-types";

type TModelsRoutingDiagramProps = {
  models?: ModelEntry[];
};

const EMPTY_MODELS: ModelEntry[] = [];

export function ModelsRoutingDiagram(props: TModelsRoutingDiagramProps) {
  const { models = EMPTY_MODELS } = props;
  const { t } = useTranslation();

  const routedModels = useMemo(
    () =>
      [...models]
        .filter((model) => model.routing_priority !== undefined)
        .sort((left, right) => (left.routing_priority ?? 0) - (right.routing_priority ?? 0)),
    [models]
  );

  if (routedModels.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-5">
      <h3 className="text-14 font-semibold text-primary">{t("agent_infra.models_tab.routing_priority")}</h3>
      <p className="mt-1 text-13 text-tertiary">Models are tried in ascending priority order.</p>

      <div className="mt-4 flex flex-col items-start gap-2">
        {routedModels.map((model, index) => (
          <div key={model.path} className="flex flex-col items-start gap-2">
            <div className="flex items-center gap-3 rounded-lg border border-subtle bg-layer-1 px-4 py-3">
              <span className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 inline-flex h-6 w-6 items-center justify-center rounded-full text-12 font-semibold">
                {model.routing_priority}
              </span>
              <div>
                <p className="text-13 font-medium text-primary">{model.name ?? model.path}</p>
                <p className="text-12 text-tertiary">{model.provider ?? "Unknown provider"}</p>
              </div>
              <span
                className={`ml-2 inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[model.status]}`}
              >
                {model.status}
              </span>
              {model.shadow_mode && (
                <span className="text-11 text-tertiary">{t("agent_infra.models_tab.shadow_mode")}</span>
              )}
            </div>
            {index < routedModels.length - 1 && <ArrowDown className="ml-6 h-4 w-4 text-tertiary" />}
          </div>
        ))}
      </div>
    </div>
  );
}
