/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Layers } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { formatUtcTimestamp, truncateContentHash } from "@/components/agent-infra/catalog-utils";
import type { TEnvironmentRevision } from "@/components/agent-infra/governance-types";
import { useEnvironmentRevisions } from "@/hooks/use-catalog";

type TRevisionsPanelProps = {
  workspaceSlug: string;
  projectId: string;
  selectedEnvironmentRef?: string;
  onRevisionSelect?: (revisionId: string) => void;
};

const EMPTY_REVISIONS: TEnvironmentRevision[] = [];

export function RevisionsPanel(props: TRevisionsPanelProps) {
  const { workspaceSlug, projectId, selectedEnvironmentRef, onRevisionSelect } = props;
  const { t } = useTranslation();
  const { revisions, isLoading, error } = useEnvironmentRevisions(workspaceSlug, projectId);

  const grouped = useMemo(() => {
    const map = new Map<string, TEnvironmentRevision[]>();
    (revisions ?? EMPTY_REVISIONS).forEach((revision) => {
      const list = map.get(revision.environment_ref) ?? [];
      list.push(revision);
      map.set(revision.environment_ref, list);
    });
    return map;
  }, [revisions]);

  const filteredRevisions = useMemo(() => {
    if (!selectedEnvironmentRef) return revisions ?? EMPTY_REVISIONS;
    return grouped.get(selectedEnvironmentRef) ?? EMPTY_REVISIONS;
  }, [grouped, revisions, selectedEnvironmentRef]);

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
        <Loader.Item height="200px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Layers className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.environments.revisions_panel")}</h3>
      </div>

      {filteredRevisions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.environments.revisions_empty")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("agent_infra.environments.environment")}</TableHead>
                <TableHead>{t("agent_infra.environments.revision")}</TableHead>
                <TableHead>{t("agent_infra.environments.status")}</TableHead>
                <TableHead>{t("agent_infra.environments.drift_status")}</TableHead>
                <TableHead>Hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRevisions.map((revision) => (
                <TableRow key={revision.id}>
                  <TableCell className="text-13 font-medium text-primary">{revision.environment_ref}</TableCell>
                  <TableCell>
                    <button
                      type="button"
                      className="text-13 text-accent-primary hover:underline"
                      onClick={() => onRevisionSelect?.(revision.id)}
                    >
                      v{revision.revision_number}
                    </button>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline-neutral" size="sm" disabled>
                      {revision.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-13 capitalize text-secondary">{revision.drift_status}</TableCell>
                  <TableCell className="font-mono text-12 text-tertiary">
                    {truncateContentHash(revision.content_hash)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
