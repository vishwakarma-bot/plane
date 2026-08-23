/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { Loader } from "@plane/ui";
import { useCatalogEnvironments } from "@/hooks/use-catalog";
import { EnvironmentsDetail } from "./environments-detail";
import { EnvironmentsList } from "./environments-list";

type TEnvironmentsSectionProps = {
  workspaceSlug: string;
  projectId: string;
};

export function EnvironmentsSection(props: TEnvironmentsSectionProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { environments, isLoading, error } = useCatalogEnvironments(workspaceSlug, projectId);
  const defaultPath = environments?.[0]?.path ?? null;
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const activePath = selectedPath ?? defaultPath;

  const selectedEnvironment = useMemo(
    () => environments?.find((environment) => environment.path === activePath),
    [environments, activePath]
  );

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
      <EnvironmentsList environments={environments} selectedPath={activePath} onEnvironmentSelect={setSelectedPath} />
      {selectedEnvironment && <EnvironmentsDetail environment={selectedEnvironment} />}
    </div>
  );
}
