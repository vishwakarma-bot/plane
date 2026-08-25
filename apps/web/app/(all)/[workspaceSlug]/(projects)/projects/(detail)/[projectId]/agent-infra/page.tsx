/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useState } from "react";
import { AlertTriangle } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { EUserProjectRoles } from "@plane/types";
// components
import {
  AgentOverview,
  ApprovalQueue,
  AssignmentPanel,
  AttentionQueue,
  DecisionHistory,
  EmergencyDenySection,
  EnvironmentsSection,
  IntegrationsSection,
  KnowledgeSection,
  ModelsSection,
  OrchestrationView,
  PoliciesSection,
  RunDetail,
  RunsLedger,
  SkillsSection,
  SoDConstraintsList,
  SyncStatus,
  WorkforceSection,
} from "@/components/agent-infra";
import { PageHead } from "@/components/core/page-title";
import { DetailedEmptyState } from "@/components/empty-state/detailed-empty-state-root";
// hooks
import { useAgentInfraAssignments, useAgentInfraOverview, useAgentInfraSyncStatus } from "@/hooks/use-agent-infra";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
import type { Route } from "./+types/page";

type TAgentInfraTab =
  | "overview"
  | "orchestration"
  | "attention"
  | "runs"
  | "knowledge"
  | "policies"
  | "workforce"
  | "skills"
  | "models"
  | "environments"
  | "integrations";

const PRIMARY_TABS: TAgentInfraTab[] = [
  "overview",
  "orchestration",
  "attention",
  "runs",
  "knowledge",
  "policies",
  "workforce",
  "skills",
  "models",
  "environments",
  "integrations",
];

function formatDistanceToNow(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const absDiffMinutes = Math.floor(Math.abs(diffMs) / 60000);

  if (absDiffMinutes < 1) return "just now";
  if (absDiffMinutes < 60) return `${absDiffMinutes} minute${absDiffMinutes === 1 ? "" : "s"} ago`;

  const absDiffHours = Math.floor(absDiffMinutes / 60);
  if (absDiffHours < 24) return `${absDiffHours} hour${absDiffHours === 1 ? "" : "s"} ago`;

  const absDiffDays = Math.floor(absDiffHours / 24);
  return `${absDiffDays} day${absDiffDays === 1 ? "" : "s"} ago`;
}

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

  const {
    isLoading: isOverviewLoading,
    error: overviewError,
    isStale: isOverviewStale,
    lastFetchedAt: overviewLastFetchedAt,
  } = useAgentInfraOverview(isFeatureEnabled ? workspaceSlug : undefined, isFeatureEnabled ? projectId : undefined);
  const {
    assignments,
    isLoading: isAssignmentsLoading,
    error: assignmentsError,
  } = useAgentInfraAssignments(isFeatureEnabled ? workspaceSlug : undefined, isFeatureEnabled ? projectId : undefined);
  const { isLoading: isSyncLoading, error: syncError } = useAgentInfraSyncStatus(
    isFeatureEnabled ? workspaceSlug : undefined,
    isFeatureEnabled ? projectId : undefined
  );

  const isLoading =
    isFeatureEnabled && canViewAgentInfra && (isOverviewLoading || isAssignmentsLoading || isSyncLoading);
  const apiError = overviewError || assignmentsError || syncError;
  const hasUnauthorizedError = isUnauthorizedError(apiError);
  const hasAssignments = (assignments?.length ?? 0) > 0;
  const [activeTab, setActiveTab] = useState<TAgentInfraTab>("overview");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const tabButtonClass = (tab: TAgentInfraTab) =>
    `whitespace-nowrap rounded-md px-3 py-1.5 text-13 font-medium transition-colors ${
      activeTab === tab ? "bg-layer-2 text-primary" : "text-tertiary hover:bg-layer-1 hover:text-secondary"
    }`;

  const renderTabBar = () => (
    <div role="tablist" className="inline-flex gap-1 self-start rounded-lg bg-surface-1 p-1">
      {PRIMARY_TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={activeTab === tab}
          className={tabButtonClass(tab)}
          onClick={() => setActiveTab(tab)}
        >
          {t(`agent_infra.tabs.${tab}`)}
        </button>
      ))}
    </div>
  );

  const renderStaleBanner = () => {
    if (!isOverviewStale) return null;

    return (
      <div className="flex items-center gap-2 rounded-md border border-warning-subtle bg-warning-subtle px-3 py-2 text-12 text-warning-primary">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>
          Showing cached data. Last updated{" "}
          {overviewLastFetchedAt ? formatDistanceToNow(overviewLastFetchedAt) : "unknown"}. Unable to reach the API —
          data may be outdated.
        </span>
      </div>
    );
  };

  const renderRunDetailOverlay = () => {
    if (!selectedRunId) return null;

    return (
      <>
        <button
          type="button"
          aria-label="Close run detail"
          className="fixed inset-0 z-20 bg-backdrop"
          onClick={() => setSelectedRunId(null)}
        />
        <div
          className="fixed top-0 right-0 bottom-0 z-25 flex w-full flex-col overflow-hidden border-l border-subtle bg-surface-1 md:w-[50%]"
          style={{
            boxShadow:
              "0px 4px 8px 0px rgba(0, 0, 0, 0.12), 0px 6px 12px 0px rgba(16, 24, 40, 0.12), 0px 1px 16px 0px rgba(16, 24, 40, 0.12)",
          }}
        >
          <RunDetail
            workspaceSlug={workspaceSlug}
            projectId={projectId}
            runId={selectedRunId}
            onClose={() => setSelectedRunId(null)}
          />
        </div>
      </>
    );
  };

  const renderTabContent = () => {
    if (activeTab === "orchestration") {
      return <OrchestrationView workspaceSlug={workspaceSlug} projectId={projectId} />;
    }

    if (activeTab === "attention") {
      return <AttentionQueue workspaceSlug={workspaceSlug} projectId={projectId} onSelectRun={setSelectedRunId} />;
    }

    if (activeTab === "runs") {
      return <RunsLedger workspaceSlug={workspaceSlug} projectId={projectId} onSelectRun={setSelectedRunId} />;
    }

    if (activeTab === "knowledge") {
      return <KnowledgeSection workspaceSlug={workspaceSlug} projectId={projectId} />;
    }

    if (activeTab === "policies") {
      return (
        <div className="flex flex-col gap-8">
          <PoliciesSection workspaceSlug={workspaceSlug} projectId={projectId} />
          <ApprovalQueue workspaceSlug={workspaceSlug} projectId={projectId} />
          <EmergencyDenySection workspaceSlug={workspaceSlug} projectId={projectId} />
          <SoDConstraintsList workspaceSlug={workspaceSlug} projectId={projectId} />
          <DecisionHistory workspaceSlug={workspaceSlug} projectId={projectId} />
        </div>
      );
    }

    if (activeTab === "workforce") {
      return <WorkforceSection workspaceSlug={workspaceSlug} projectId={projectId} />;
    }

    if (activeTab === "skills") {
      return <SkillsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
    }

    if (activeTab === "models") {
      return <ModelsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
    }

    if (activeTab === "environments") {
      return <EnvironmentsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
    }

    if (activeTab === "integrations") {
      return <IntegrationsSection workspaceSlug={workspaceSlug} projectId={projectId} />;
    }

    return (
      <>
        <AgentOverview
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          showSyncStatus={false}
          showAttentionQueue={false}
        />
        <AssignmentPanel workspaceSlug={workspaceSlug} projectId={projectId} assignments={assignments} />
      </>
    );
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
              router.push(`/${workspaceSlug}/settings/projects/${projectId}/`);
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

  if (isLoading && activeTab === "overview") {
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

  if (!hasAssignments && activeTab === "overview") {
    return (
      <div className="flex h-full w-full flex-col overflow-y-auto">
        <PageHead title={pageTitle} />
        <div className="border-b border-subtle px-6 py-4 lg:hidden">
          <SyncStatus workspaceSlug={workspaceSlug} projectId={projectId} />
        </div>
        <div className="flex flex-col gap-6 p-6">
          {renderTabBar()}
          {renderStaleBanner()}
          <div role="tabpanel" className="grid w-full place-items-center bg-surface-1 px-6 py-16">
            <EmptyStateDetailed
              title={t("agent_infra.empty_state.title")}
              description={t("agent_infra.empty_state.description")}
              assetKey="project"
              assetClassName="size-40"
            />
          </div>
        </div>
        {renderRunDetailOverlay()}
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
        {renderStaleBanner()}

        <div role="tabpanel">{renderTabContent()}</div>
      </div>
      {renderRunDetailOverlay()}
    </div>
  );
}

export default observer(ProjectAgentInfraPage);
