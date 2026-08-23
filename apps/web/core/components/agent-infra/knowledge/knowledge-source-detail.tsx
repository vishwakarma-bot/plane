/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ExternalLink } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/ui";
import { KnowledgeVersionTimeline } from "./knowledge-version-timeline";
import type { TKnowledgeSource, TKnowledgeVersion } from "./knowledge-types";
import {
  getSourceLifecycleStatus,
  getStalenessLevel,
  STALENESS_DOT_CLASSES,
} from "./knowledge-utils";

type TKnowledgeSourceDetailProps = {
  source: TKnowledgeSource;
  versions?: TKnowledgeVersion[];
  versionsLoading?: boolean;
  onVersionSelect?: (versionId: string) => void;
};

function lifecycleBadgeLabel(source: TKnowledgeSource, t: (key: string) => string): string {
  const status = getSourceLifecycleStatus(source);
  if (status === "retired") return t("agent_infra.knowledge.retired");
  if (status === "expired") return t("agent_infra.knowledge.expired");
  return status;
}

export function KnowledgeSourceDetail(props: TKnowledgeSourceDetailProps) {
  const { source, versions, versionsLoading = false, onVersionSelect } = props;
  const { t } = useTranslation();
  const lifecycleStatus = getSourceLifecycleStatus(source);
  const staleness = getStalenessLevel(source);

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-lg border border-subtle bg-surface-1 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${STALENESS_DOT_CLASSES[staleness]}`} />
              <h3 className="text-16 font-semibold text-primary">{source.name}</h3>
            </div>
            <p className="mt-1 text-13 capitalize text-tertiary">
              {source.source_type} · {source.authority_type}
            </p>
          </div>
          <Badge
            variant={
              lifecycleStatus === "active"
                ? "accent-success"
                : lifecycleStatus === "expired"
                  ? "accent-destructive"
                  : "outline-neutral"
            }
            size="sm"
            disabled
          >
            {lifecycleBadgeLabel(source, t)}
          </Badge>
        </div>

        <dl className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-11 text-tertiary">{t("agent_infra.knowledge.sensitivity")}</dt>
            <dd className="mt-1 capitalize text-13 text-primary">{source.sensitivity}</dd>
          </div>
          <div>
            <dt className="text-11 text-tertiary">Owner</dt>
            <dd className="mt-1 text-13 text-primary">{source.owner ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-11 text-tertiary">URL</dt>
            <dd className="mt-1 text-13 text-primary">
              {source.url ? (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-accent-primary hover:underline"
                >
                  {source.url}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : (
                "—"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-11 text-tertiary">Effective range</dt>
            <dd className="mt-1 text-13 text-primary">
              {source.effective_from ? new Date(source.effective_from).toLocaleDateString() : "—"} –{" "}
              {source.expires_at ? new Date(source.expires_at).toLocaleDateString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-11 text-tertiary">Retention policy</dt>
            <dd className="mt-1 text-13 text-primary">{source.retention_days} days</dd>
          </div>
          <div>
            <dt className="text-11 text-tertiary">Retirement</dt>
            <dd className="mt-1 text-13 text-primary">
              {source.is_retired
                ? `${t("agent_infra.knowledge.retired")}${source.retired_at ? ` (${new Date(source.retired_at).toLocaleString()})` : ""}`
                : "Active"}
            </dd>
          </div>
        </dl>
      </div>

      <div>
        <h4 className="mb-3 text-14 font-semibold text-primary">{t("agent_infra.knowledge.versions")}</h4>
        <KnowledgeVersionTimeline
          versions={versions}
          isLoading={versionsLoading}
          onVersionSelect={onVersionSelect}
        />
      </div>
    </div>
  );
}
