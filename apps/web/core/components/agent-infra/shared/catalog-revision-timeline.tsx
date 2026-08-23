/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Clock3, History } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TBadgeVariant } from "@plane/ui";
import { Badge, Loader } from "@plane/ui";
import type { TCatalogEntityType, TCatalogRevision } from "@/components/agent-infra/governance-types";
import { formatUtcTimestamp, truncateContentHash } from "../catalog-utils";
import { CatalogRevisionActions } from "./catalog-revision-actions";

type TCatalogRevisionTimelineProps = {
  workspaceSlug: string;
  projectId: string;
  entityType: TCatalogEntityType;
  entityRef?: string;
  revisions?: TCatalogRevision[];
  isLoading?: boolean;
  error?: unknown;
  onMutate?: () => Promise<void> | void;
};

const EMPTY_REVISIONS: TCatalogRevision[] = [];

const REVISION_STATUS_VARIANTS: Record<string, TBadgeVariant> = {
  draft: "outline-neutral",
  pending_approval: "accent-warning",
  approved: "accent-success",
  rejected: "accent-destructive",
  rolled_back: "outline-neutral",
};

function renderDiffSummary(diff?: TCatalogRevision["diff_summary"]) {
  if (!diff) return null;

  const parts: string[] = [];
  if (diff.added?.length) parts.push(`+${diff.added.join(", ")}`);
  if (diff.removed?.length) parts.push(`-${diff.removed.join(", ")}`);
  if (diff.changed) {
    parts.push(
      ...Object.entries(diff.changed).map(
        ([field, change]) => `${field}: ${String(change.old)} → ${String(change.new)}`
      )
    );
  }

  if (parts.length === 0) return null;
  return <p className="mt-2 text-13 leading-5 text-secondary">{parts.join(" · ")}</p>;
}

export function CatalogRevisionTimeline(props: TCatalogRevisionTimelineProps) {
  const {
    workspaceSlug,
    projectId,
    entityRef,
    revisions = EMPTY_REVISIONS,
    isLoading = false,
    error,
    onMutate,
  } = props;
  const { t } = useTranslation();

  if (error) {
    return (
      <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-4 py-6 text-center text-13 text-tertiary">
        {t("agent_infra.governance.revision_error")}
      </div>
    );
  }

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="72px" />
        <Loader.Item height="72px" />
      </Loader>
    );
  }

  if (!entityRef) {
    return (
      <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-4 py-6 text-center text-13 text-tertiary">
        {t("agent_infra.governance.select_entity_for_history")}
      </div>
    );
  }

  if (revisions.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-4 py-6 text-center text-13 text-tertiary">
        {t("agent_infra.governance.no_revisions")}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <History className="h-4 w-4 text-tertiary" />
        <h4 className="text-14 font-semibold text-primary">{t("agent_infra.governance.version_history")}</h4>
      </div>

      <div className="relative space-y-0">
        <div className="absolute bottom-2 left-[11px] top-2 w-px bg-subtle" aria-hidden />

        {revisions.map((revision) => (
          <div key={revision.id} className="relative flex gap-4 pb-6 last:pb-0">
            <div className="relative z-10 mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border-2 border-surface-1 bg-accent-primary" />

            <div className="min-w-0 flex-1 rounded-lg border border-subtle bg-surface-1 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-14 font-semibold text-primary">v{revision.revision_number}</span>
                <Badge
                  variant={REVISION_STATUS_VARIANTS[revision.status] ?? "outline-neutral"}
                  size="sm"
                  disabled
                >
                  {revision.status.replace("_", " ")}
                </Badge>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-11 text-tertiary">
                <span className="font-mono">{truncateContentHash(revision.content_hash)}</span>
                {revision.created_at && (
                  <span className="inline-flex items-center gap-1">
                    <Clock3 className="h-3 w-3" />
                    {formatUtcTimestamp(revision.created_at)}
                  </span>
                )}
              </div>

              {renderDiffSummary(revision.diff_summary ?? undefined)}

              {revision.approved_at && (
                <p className="mt-2 text-11 text-tertiary">
                  {t("agent_infra.governance.approved_at", { date: formatUtcTimestamp(revision.approved_at) })}
                </p>
              )}

              <div className="mt-3 border-t border-subtle pt-3">
                <CatalogRevisionActions
                  workspaceSlug={workspaceSlug}
                  projectId={projectId}
                  revision={revision}
                  onActionComplete={onMutate}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
