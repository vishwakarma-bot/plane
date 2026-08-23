/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { Loader } from "@plane/ui";
import { useCatalogModels } from "@/hooks/use-catalog";
import { ModelsList } from "./models-list";
import { ModelsRoutingDiagram } from "./models-routing-diagram";

type TModelsSectionProps = {
  workspaceSlug: string;
  projectId: string;
};

export function ModelsSection(props: TModelsSectionProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { models, isLoading, error } = useCatalogModels(workspaceSlug, projectId);

  if (error) {
    return (
      <div className="grid place-items-center rounded-lg border border-subtle bg-surface-1 px-6 py-16">
        <EmptyStateDetailed
          title={t("agent_infra.error_state.title")}
          description={t("agent_infra.error_state.description")}
          assetKey="project"
          assetClassName="size-32"
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <Loader className="space-y-4">
        <Loader.Item height="48px" />
        <Loader.Item height="280px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <ModelsRoutingDiagram models={models} />
      <ModelsList models={models} />
    </div>
  );
}
