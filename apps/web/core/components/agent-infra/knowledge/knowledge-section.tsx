/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { Loader } from "@plane/ui";
import { useKnowledgeSources, useKnowledgeVersions } from "@/hooks/use-knowledge";
import { KnowledgeConflictBanner } from "./knowledge-conflict-banner";
import { KnowledgeSourceDetail } from "./knowledge-source-detail";
import { KnowledgeSourceList } from "./knowledge-source-list";
import { detectKnowledgeConflicts, getStaleSources } from "./knowledge-utils";

type TKnowledgeSectionProps = {
  workspaceSlug: string;
  projectId: string;
};

export function KnowledgeSection(props: TKnowledgeSectionProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { sources, isLoading, error } = useKnowledgeSources(workspaceSlug, projectId);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);

  const { versions, isLoading: versionsLoading } = useKnowledgeVersions(
    workspaceSlug,
    projectId,
    selectedSourceId ?? undefined
  );

  useEffect(() => {
    if (!selectedSourceId && sources?.length) {
      setSelectedSourceId(sources[0].id);
    }
  }, [selectedSourceId, sources]);

  const selectedSource = useMemo(
    () => sources?.find((source) => source.id === selectedSourceId),
    [sources, selectedSourceId]
  );

  const versionsBySource = useMemo(() => {
    if (!selectedSourceId || !versions) return {};
    return { [selectedSourceId]: versions };
  }, [selectedSourceId, versions]);

  const conflicts = useMemo(
    () => (sources ? detectKnowledgeConflicts(sources, versionsBySource) : []),
    [sources, versionsBySource]
  );
  const staleSources = useMemo(() => (sources ? getStaleSources(sources) : []), [sources]);

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

      <KnowledgeSourceList
        sources={sources}
        onSourceSelect={setSelectedSourceId}
      />

      {selectedSource && (
        <KnowledgeSourceDetail
          source={selectedSource}
          versions={versions}
          versionsLoading={versionsLoading}
        />
      )}
    </div>
  );
}
