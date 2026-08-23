/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { Loader } from "@plane/ui";
import { useCatalogWorkforce } from "@/hooks/use-catalog";
import { WorkforceDetail } from "./workforce-detail";
import { WorkforceList } from "./workforce-list";

type TWorkforceSectionProps = {
  workspaceSlug: string;
  projectId: string;
};

export function WorkforceSection(props: TWorkforceSectionProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { agents, isLoading, error } = useCatalogWorkforce(workspaceSlug, projectId);
  const defaultPath = agents?.[0]?.path ?? null;
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const activePath = selectedPath ?? defaultPath;

  const selectedAgent = useMemo(() => agents?.find((agent) => agent.path === activePath), [agents, activePath]);

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
      <WorkforceList agents={agents} selectedPath={activePath} onAgentSelect={setSelectedPath} />
      {selectedAgent && <WorkforceDetail agent={selectedAgent} />}
    </div>
  );
}
