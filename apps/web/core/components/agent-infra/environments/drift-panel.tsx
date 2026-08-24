/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Loader } from "@plane/ui";
import { DRIFT_STATUS_CLASSES, formatUtcTimestamp } from "@/components/agent-infra/catalog-utils";
import type { TEnvironmentRevision } from "@/components/agent-infra/governance-types";
import { useEnvironmentRevisions } from "@/hooks/use-catalog";
import catalogService from "@/services/catalog.service";

type TDriftPanelProps = {
  workspaceSlug: string;
  projectId: string;
  selectedRevisionId?: string | null;
};

const EMPTY_REVISIONS: TEnvironmentRevision[] = [];

export function DriftPanel(props: TDriftPanelProps) {
  const { workspaceSlug, projectId, selectedRevisionId } = props;
  const { t } = useTranslation();
  const { revisions, isLoading, error, mutate } = useEnvironmentRevisions(workspaceSlug, projectId);
  const [checkingId, setCheckingId] = useState<string | null>(null);

  const activeRevisions = useMemo(
    () => (revisions ?? EMPTY_REVISIONS).filter((revision) => revision.status === "active"),
    [revisions]
  );

  const selectedRevision = useMemo(() => {
    if (selectedRevisionId) {
      return (revisions ?? EMPTY_REVISIONS).find((revision) => revision.id === selectedRevisionId);
    }
    return activeRevisions[0];
  }, [activeRevisions, revisions, selectedRevisionId]);

  const handleDriftCheck = useCallback(
    async (revisionId: string, contentHash: string) => {
      setCheckingId(revisionId);
      try {
        await catalogService.triggerDriftCheck(workspaceSlug, projectId, revisionId, contentHash);
        await mutate();
      } finally {
        setCheckingId(null);
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
        <Loader.Item height="160px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.environments.drift_panel")}</h3>
      </div>

      {activeRevisions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.environments.drift_empty")}
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {activeRevisions.map((revision) => (
              <div key={revision.id} className="rounded-lg border border-subtle bg-surface-1 p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-13 font-semibold text-primary">{revision.environment_ref}</p>
                  <span
                    className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${DRIFT_STATUS_CLASSES[revision.drift_status] ?? DRIFT_STATUS_CLASSES.unknown}`}
                  >
                    {revision.drift_status.replace("_", " ")}
                  </span>
                </div>
                <p className="mt-2 text-11 text-tertiary">
                  {t("agent_infra.environments.last_check", {
                    date: formatUtcTimestamp(revision.last_drift_check_at),
                  })}
                </p>
                <Button
                  variant="neutral-primary"
                  size="sm"
                  className="mt-3"
                  disabled={checkingId === revision.id}
                  onClick={() => handleDriftCheck(revision.id, revision.content_hash)}
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  {t("agent_infra.environments.run_drift_check")}
                </Button>
              </div>
            ))}
          </div>

          {selectedRevision && (
            <div className="rounded-lg border border-subtle bg-surface-1 p-4">
              <h4 className="text-13 font-semibold text-primary">
                {t("agent_infra.environments.revision_detail")} — {selectedRevision.environment_ref} v
                {selectedRevision.revision_number}
              </h4>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-11 text-tertiary uppercase">{t("agent_infra.environments.status")}</dt>
                  <dd className="mt-1 text-13 text-primary">{selectedRevision.status}</dd>
                </div>
                <div>
                  <dt className="text-11 text-tertiary uppercase">{t("agent_infra.environments.drift_status")}</dt>
                  <dd className="mt-1 text-13 text-primary capitalize">
                    {selectedRevision.drift_status.replace("_", " ")}
                  </dd>
                </div>
              </dl>
              {selectedRevision.drift_detail && (
                <div className="mt-4 rounded-md bg-layer-2 p-3 text-12 text-secondary">
                  <pre className="overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(selectedRevision.drift_detail, null, 2)}
                  </pre>
                </div>
              )}
              {selectedRevision.snapshot && (
                <div className="mt-4">
                  <p className="text-11 text-tertiary uppercase">{t("agent_infra.environments_tab.snapshot")}</p>
                  <pre className="mt-2 overflow-x-auto rounded-md bg-layer-2 p-3 text-12 text-secondary">
                    {JSON.stringify(selectedRevision.snapshot, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
