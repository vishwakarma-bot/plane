/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Bot, Clock3 } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TBadgeVariant } from "@plane/ui";
import { Badge, Loader } from "@plane/ui";
import type { TKnowledgeVersion, TVersionStatus } from "./knowledge-types";
import { truncateHash } from "./knowledge-utils";
import { VersionReviewActions } from "./version-review-actions";

type TKnowledgeVersionTimelineProps = {
  versions?: TKnowledgeVersion[];
  isLoading?: boolean;
  onVersionSelect?: (versionId: string) => void;
  onVersionStatusChange?: (versionId: string, newStatus: TVersionStatus) => Promise<void>;
};

const EMPTY_VERSIONS: TKnowledgeVersion[] = [];
const VERSION_STATUS_VARIANTS: Record<TVersionStatus, TBadgeVariant> = {
  draft: "outline-neutral",
  review: "accent-primary",
  approved: "accent-success",
  rejected: "accent-destructive",
  superseded: "outline-neutral",
  quarantined: "accent-warning",
};

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")} ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

export function KnowledgeVersionTimeline(props: TKnowledgeVersionTimelineProps) {
  const { versions = EMPTY_VERSIONS, isLoading = false, onVersionSelect, onVersionStatusChange } = props;
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="72px" />
        <Loader.Item height="72px" />
      </Loader>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-4 py-8 text-center text-13 text-tertiary">
        {t("agent_infra.knowledge.versions")}
      </div>
    );
  }

  return (
    <div className="relative space-y-0">
      <div className="bg-subtle absolute top-2 bottom-2 left-[11px] w-px" aria-hidden />

      {versions.map((version) => {
        const isSuperseded = version.status === "superseded";

        return (
          <div key={version.id} className="relative flex gap-4 pb-6 last:pb-0">
            <div className="border-surface-1 relative z-10 mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border-2 bg-accent-primary" />

            <div className="min-w-0 flex-1 rounded-lg border border-subtle bg-surface-1 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="text-14 font-semibold text-primary hover:text-accent-primary"
                  onClick={() => onVersionSelect?.(version.id)}
                >
                  v{version.version_number}
                </button>
                <Badge
                  variant={VERSION_STATUS_VARIANTS[version.status]}
                  size="sm"
                  disabled
                  className={isSuperseded ? "line-through" : undefined}
                >
                  {version.status}
                </Badge>
                {version.is_agent_generated && (
                  <Badge variant="outline-neutral" size="sm" disabled>
                    <Bot className="mr-1 h-3 w-3" />
                    {t("agent_infra.knowledge.agent_generated")}
                  </Badge>
                )}
                {version.status === "quarantined" && (
                  <Badge variant="accent-warning" size="sm" disabled>
                    {t("agent_infra.knowledge.quarantined")}
                  </Badge>
                )}
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-11 text-tertiary">
                <span className="font-mono">{truncateHash(version.content_hash)}</span>
                <span className="inline-flex items-center gap-1">
                  <Clock3 className="h-3 w-3" />
                  {formatTimestamp(version.created_at)}
                </span>
              </div>

              {version.diff_summary && <p className="mt-2 text-13 leading-5 text-secondary">{version.diff_summary}</p>}

              {version.status === "approved" && (version.promoted_by || version.promoted_at) && (
                <p className="mt-2 text-11 text-tertiary">
                  Promoted {version.promoted_at ? formatTimestamp(version.promoted_at) : "—"}
                  {version.promoted_by ? ` by ${version.promoted_by}` : ""}
                </p>
              )}

              {onVersionStatusChange && version.status !== "superseded" && (
                <div className="mt-3 border-t border-subtle pt-3">
                  <VersionReviewActions version={version} onStatusChange={onVersionStatusChange} />
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
