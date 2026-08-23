/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useState } from "react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { EUserProjectRoles } from "@plane/types";
// components
import {
  AgentOverview,
  AssignmentPanel,
  AttentionQueue,
  EnvironmentsSection,
  IntegrationsSection,
  KnowledgeSection,
  ModelsSection,
  SkillsSection,
  SyncStatus,
  WorkforceSection,
} from "@/components/agent-infra";
import { PageHead } from "@/components/core/page-title";
import { DetailedEmptyState } from "@/components/empty-state/detailed-empty-state-root";
// hooks
import {
  useAgentInfraAssignments,
  useAgentInfraAttentionItems,
  useAgentInfraOverview,
  useAgentInfraSyncStatus,
} from "@/hooks/use-agent-infra";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
import type { Route } from "./+types/page";

type TAgentInfraTab = "overview" | "knowledge" | "workforce" | "skills" | "models" | "environments" | "integrations";

const AGENT_INFRA_TABS: TAgentInfraTab[] = [
  "overview",
  "knowledge",
  "workforce",
  "skills",
  "models",
  "environments",
  "integrations",
];

function isUnauthorizedError(error: unknown) {
  if (!error || typeof error !== "object") return false;

  const statusCode =
    "status_code" in error && typeof error.status_code === "number"
      ? error.status_code
      : "status" in error && typeof error.status === "number"
        ? error.status
        : undefined;

  return statusCode === 403;
}

function ProjectAgentInfraPage({ params }: Route.ComponentProps) {
  const router = useAppRouter();
  const { workspaceSlug, projectId } = params;
  const { t } = useTranslation();
  const { currentProjectDetails, getProjectById } = useProject();
  const { allowPermissions } = useUserPermissions();

  const project = getProjectById(projectId);
  const pageTitle = project?.name
    ? t("agent_infra.page_label", { project: project.name })
    : t("agent_infra.page_label", { project: "Plane" });

  const canViewAgentInfra = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER, EUserPermissions.GUEST],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );
  const canManageFeatures = allowPermissions([EUserProjectRoles.ADMIN], EUserPermissionsLevel.PROJECT);

  const isFeatureEnabled = currentProjectDetails?.is_agent_infra_enabled ?? false;

  const { isLoading: isOverviewLoading, error: overviewError } = useAgentInfraOverview(
    isFeatureEnabled ? workspaceSlug : undefined,
    isFeatureEnabled ? projectId : undefined
  );
  const {
    assignments,
    isLoading: isAssignmentsLoading,
    error: assignmentsError,
  } = useAgentInfraAssignments(isFeatureEnabled ? workspaceSlug : undefined, isFeatureEnabled ? projectId : undefined);
  const {
    items: attentionItems,
    isLoading: isAttentionLoading,
    error: attentionError,
  } = useAgentInfraAttentionItems(
    isFeatureEnabled ? workspaceSlug : undefined,
    isFeatureEnabled ? projectId : undefined
  );
  const { isLoading: isSyncLoading, error: syncError } = useAgentInfraSyncStatus(
    isFeatureEnabled ? workspaceSlug : undefined,
    isFeatureEnabled ? projectId : undefined
  );

  const isOverviewDataLoading =
    isFeatureEnabled &&
    canViewAgentInfra &&
    (isOverviewLoading || isAssignmentsLoading || isAttentionLoading || isSyncLoading);
  const overviewApiError = overviewError || assignmentsError || attentionError || syncError;
  const hasUnauthorizedError = isUnauthorizedError(overviewApiError);
  const hasAssignments = (assignments?.length ?? 0) > 0;
  const [activeTab, setActiveTab] = useState<TAgentInfraTab>("overview");

  const tabButtonClass = (tab: TAgentInfraTab) =>
    `whitespace-nowrap rounded-md px-3 py-1.5 text-13 font-medium transition-colors ${
      activeTab === tab ? "bg-layer-2 text-primary" : "text-tertiary hover:bg-layer-1 hover:text-secondary"
    }`;

  const renderTabBar = () => (
    <div className="inline-flex max-w-full gap-1 self-start overflow-x-auto rounded-lg bg-surface-1 p-1">
      {AGENT_INFRA_TABS.map((tab) => (
        <button key={tab} type="button" className={tabButtonClass(tab)} onClick={() => setActiveTab(tab)}>
          {t(`agent_infra.tabs.${tab}`)}
        </button>
      ))}
    </div>
  );

  const renderActiveTab = () => {
    switch (activeTab) {
      case "knowledge":
        return <KnowledgeSection workspaceSlug={workspaceSlug} projectId={projectId} />;
      case "workforce":
        return <WorkforceSection workspaceSlug={workspaceSlug} projectId={projectId} />;
      case "skills":
        return <SkillsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
      case "models":
        return <ModelsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
      case "environments":
        return <EnvironmentsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
      case "integrations":
        return <IntegrationsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
      case "overview":
      default:
        if (!hasAssignments) {
          return (
            <div className="grid h-full w-full place-items-center bg-surface-1 px-6">
              <EmptyStateDetailed
                title={t("agent_infra.empty_state.title")}
                description={t("agent_infra.empty_state.description")}
                assetKey="project"
                assetClassName="size-40"
              />
            </div>
          );
        }

        return (
          <>
            <AgentOverview
              workspaceSlug={workspaceSlug}
              projectId={projectId}
              showSyncStatus={false}
              showAttentionQueue={false}
            />

            {(attentionItems?.length ?? 0) > 0 && (
              <AttentionQueue workspaceSlug={workspaceSlug} projectId={projectId} items={attentionItems} />
            )}

            <AssignmentPanel workspaceSlug={workspaceSlug} projectId={projectId} assignments={assignments} />
          </>
        );
    }
  };

  if (!canViewAgentInfra) {
    return (
      <div className="grid h-full w-full place-items-center bg-surface-1">
        <EmptyStateDetailed
          title={t("agent_infra.unauthorized_state.title")}
          description={t("agent_infra.unauthorized_state.description")}
          assetKey="no-access"
          assetClassName="size-40"
        />
      </div>
    );
  }

  if (!isFeatureEnabled) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <DetailedEmptyState
          title={t("disabled_project.empty_state.agent_infra.title")}
          description={t("disabled_project.empty_state.agent_infra.description")}
          primaryButton={{
            text: t("disabled_project.empty_state.agent_infra.primary_button.text"),
            onClick: () => {
              router.push(`/${workspaceSlug}/settings/projects/${projectId}/features`);
            },
            disabled: !canManageFeatures,
          }}
        />
      </div>
    );
  }

  if (hasUnauthorizedError) {
    return (
      <div className="grid h-full w-full place-items-center bg-surface-1">
        <EmptyStateDetailed
          title={t("agent_infra.unauthorized_state.title")}
          description={t("agent_infra.unauthorized_state.description")}
          assetKey="no-access"
          assetClassName="size-40"
        />
      </div>
    );
  }

  if (overviewApiError && !isOverviewDataLoading && activeTab === "overview") {
    return (
      <div className="grid h-full w-full place-items-center bg-surface-1">
        <EmptyStateDetailed
          title={t("agent_infra.error_state.title")}
          description={t("agent_infra.error_state.description")}
          assetKey="project"
          assetClassName="size-40"
        />
      </div>
    );
  }

  if (isOverviewDataLoading && activeTab === "overview") {
    return (
      <div className="h-full w-full overflow-y-auto p-6">
        <PageHead title={pageTitle} />
        <AgentOverview
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          showSyncStatus={false}
          showAttentionQueue={false}
          isLoading
        />
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-y-auto">
      <PageHead title={pageTitle} />
      <div className="flex flex-col gap-6 p-6">
        <div className="border-b border-subtle pb-4 lg:hidden">
          <SyncStatus workspaceSlug={workspaceSlug} projectId={projectId} />
        </div>

        {renderTabBar()}
        {renderActiveTab()}
      </div>
    </div>
  );
}

export default observer(ProjectAgentInfraPage);
