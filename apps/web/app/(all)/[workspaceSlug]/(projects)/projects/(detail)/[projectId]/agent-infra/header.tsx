/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { useTranslation } from "@plane/i18n";
import { AiIcon } from "@plane/propel/icons";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { SyncStatus } from "@/components/agent-infra";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { CommonProjectBreadcrumbs } from "@/components/breadcrumbs/common";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useAppRouter } from "@/hooks/use-app-router";

export const AgentInfraHeader = observer(function AgentInfraHeader() {
  const router = useAppRouter();
  const { workspaceSlug, projectId } = useParams();
  const { currentProjectDetails, loader } = useProject();
  const { t } = useTranslation();

  const isFeatureEnabled = currentProjectDetails?.is_agent_infra_enabled ?? false;

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs onBack={router.back} isLoading={loader === "init-loader"}>
          <CommonProjectBreadcrumbs workspaceSlug={workspaceSlug?.toString()} projectId={projectId?.toString()} />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("sidebar.agent_infra")}
                href={`/${workspaceSlug}/projects/${currentProjectDetails?.id}/agent-infra/`}
                icon={<AiIcon className="h-4 w-4 text-tertiary" />}
                isLast
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
      {isFeatureEnabled && workspaceSlug && projectId && (
        <Header.RightItem>
          <div className="hidden min-w-[280px] lg:block">
            <SyncStatus workspaceSlug={workspaceSlug.toString()} projectId={projectId.toString()} />
          </div>
        </Header.RightItem>
      )}
    </Header>
  );
});
