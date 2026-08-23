/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import { AlertTriangle, Plus } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { Loader } from "@plane/ui";
import {
  useKnowledgeConflicts,
  useKnowledgeIndexRecords,
  useKnowledgeSources,
  useKnowledgeVersions,
} from "@/hooks/use-knowledge";
import knowledgeService from "@/services/knowledge.service";
import { ConflictResolutionPanel } from "./conflict-resolution-panel";
import { IndexRecordsSection } from "./index-records-section";
import { KnowledgeConflictBanner } from "./knowledge-conflict-banner";
import { KnowledgeSourceDetail } from "./knowledge-source-detail";
import { KnowledgeSourceForm } from "./knowledge-source-form";
import { KnowledgeSourceList } from "./knowledge-source-list";
import type { TKnowledgeSource, TVersionStatus } from "./knowledge-types";
import { detectKnowledgeConflicts, getStaleSources } from "./knowledge-utils";

type TKnowledgeSectionProps = {
  workspaceSlug: string;
  projectId: string;
};

export function KnowledgeSection(props: TKnowledgeSectionProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { sources, isLoading, error, mutate: mutateSources } = useKnowledgeSources(workspaceSlug, projectId);
  const defaultSourceId = sources?.[0]?.id ?? null;
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState<"create" | "edit" | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const activeSourceId = selectedSourceId ?? defaultSourceId;

  const { versions, isLoading: versionsLoading, mutate: mutateVersions } = useKnowledgeVersions(
    workspaceSlug,
    projectId,
    activeSourceId ?? undefined
  );

  const { conflicts: conflictRecords, isLoading: conflictsLoading, mutate: mutateConflicts } =
    useKnowledgeConflicts(workspaceSlug, projectId);

  const { records: indexRecords, isLoading: indexLoading } =
    useKnowledgeIndexRecords(workspaceSlug, projectId);

  const selectedSource = useMemo(
    () => sources?.find((source) => source.id === activeSourceId),
    [sources, activeSourceId]
  );

  const versionsBySource = useMemo(() => {
    if (!activeSourceId || !versions) return {};
    return { [activeSourceId]: versions };
  }, [activeSourceId, versions]);

  const conflicts = useMemo(
    () => (sources ? detectKnowledgeConflicts(sources, versionsBySource) : []),
    [sources, versionsBySource]
  );
  const staleSources = useMemo(() => (sources ? getStaleSources(sources) : []), [sources]);

  const handleCreateSource = useCallback(
    async (data: Partial<TKnowledgeSource>) => {
      setFormSubmitting(true);
      try {
        await knowledgeService.createSource(workspaceSlug, projectId, data);
        await mutateSources();
        setShowForm(null);
      } finally {
        setFormSubmitting(false);
      }
    },
    [workspaceSlug, projectId, mutateSources]
  );

  const handleUpdateSource = useCallback(
    async (data: Partial<TKnowledgeSource>) => {
      if (!activeSourceId) return;
      setFormSubmitting(true);
      try {
        await knowledgeService.updateSource(workspaceSlug, projectId, activeSourceId, data);
        await mutateSources();
        setShowForm(null);
      } finally {
        setFormSubmitting(false);
      }
    },
    [workspaceSlug, projectId, activeSourceId, mutateSources]
  );

  const handleRetireSource = useCallback(async () => {
    if (!activeSourceId) return;
    if (!window.confirm("Are you sure you want to retire this knowledge source? This will trigger index deletion for all approved versions.")) return;
    await knowledgeService.retireSource(workspaceSlug, projectId, activeSourceId);
    await mutateSources();
    setSelectedSourceId(null);
  }, [workspaceSlug, projectId, activeSourceId, mutateSources]);

  const handleVersionStatusChange = useCallback(
    async (versionId: string, newStatus: TVersionStatus) => {
      if (!activeSourceId) return;
      await knowledgeService.updateVersionStatus(workspaceSlug, projectId, activeSourceId, versionId, newStatus);
      await mutateVersions();
    },
    [workspaceSlug, projectId, activeSourceId, mutateVersions]
  );

  const handleResolveConflict = useCallback(
    async (conflictId: string, data: { status: string; resolution_summary: string; winning_version?: string }) => {
      await knowledgeService.resolveConflict(workspaceSlug, projectId, conflictId, data);
      await mutateConflicts();
    },
    [workspaceSlug, projectId, mutateConflicts]
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
      {conflicts.map((conflict) => (
        <KnowledgeConflictBanner
          key={conflict.sourceId}
          conflict={conflict}
          onCompareVersion={(sourceId) => setSelectedSourceId(sourceId)}
        />
      ))}

      {staleSources.length > 0 && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-950/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <div>
            <p className="text-14 font-semibold text-amber-900 dark:text-amber-100">
              {staleSources.length} source{staleSources.length === 1 ? "" : "s"} approaching expiry or expired
            </p>
            <p className="mt-1 text-13 text-amber-800 dark:text-amber-200">
              {staleSources.map((source) => source.name).join(", ")}
            </p>
          </div>
        </div>
      )}

      {showForm === "create" && (
        <KnowledgeSourceForm
          onSubmit={handleCreateSource}
          onCancel={() => setShowForm(null)}
          isSubmitting={formSubmitting}
        />
      )}
      {showForm === "edit" && selectedSource && (
        <KnowledgeSourceForm
          source={selectedSource}
          onSubmit={handleUpdateSource}
          onCancel={() => setShowForm(null)}
          isSubmitting={formSubmitting}
        />
      )}

      <div className="flex items-center justify-between">
        <div />
        <div className="flex items-center gap-2">
          {selectedSource && !selectedSource.is_retired && (
            <>
              <Button variant="outline-neutral" size="sm" onClick={() => setShowForm("edit")}>
                Edit Source
              </Button>
              <Button
                variant="outline-neutral"
                size="sm"
                onClick={handleRetireSource}
                className="text-red-600 hover:text-red-700"
              >
                Retire
              </Button>
            </>
          )}
          <Button variant="primary" size="sm" onClick={() => setShowForm("create")}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            Register Source
          </Button>
        </div>
      </div>

      <KnowledgeSourceList
        sources={sources}
        onSourceSelect={setSelectedSourceId}
      />

      {selectedSource && (
        <KnowledgeSourceDetail
          source={selectedSource}
          versions={versions}
          versionsLoading={versionsLoading}
          onVersionSelect={() => {}}
          onVersionStatusChange={handleVersionStatusChange}
        />
      )}

      <ConflictResolutionPanel
        conflicts={conflictRecords ?? []}
        isLoading={conflictsLoading}
        onResolve={handleResolveConflict}
      />

      <IndexRecordsSection
        records={indexRecords ?? []}
        isLoading={indexLoading}
      />
    </div>
  );
}
