/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { BookOpen } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import type { TAuthorityType, TKnowledgeSource, TSourceType } from "./knowledge-types";
import {
  AUTHORITY_BADGE_CLASSES,
  getSourceLifecycleStatus,
  getStalenessLevel,
  STALENESS_DOT_CLASSES,
} from "./knowledge-utils";

type TKnowledgeSourceListProps = {
  sources?: TKnowledgeSource[];
  isLoading?: boolean;
  onSourceSelect?: (sourceId: string) => void;
};

const SOURCE_TYPES: TSourceType[] = ["plane", "repository", "ci", "incident", "external"];
const AUTHORITY_TYPES: TAuthorityType[] = [
  "product",
  "design",
  "architecture",
  "qa",
  "security",
  "platform",
  "release",
];

function lifecycleBadgeLabel(source: TKnowledgeSource, t: (key: string) => string): string {
  const status = getSourceLifecycleStatus(source);
  if (status === "retired") return t("agent_infra.knowledge.retired");
  if (status === "expired") return t("agent_infra.knowledge.expired");
  return status;
}

export function KnowledgeSourceList(props: TKnowledgeSourceListProps) {
  const { sources = [], isLoading = false, onSourceSelect } = props;
  const { t } = useTranslation();
  const [sourceTypeFilter, setSourceTypeFilter] = useState<TSourceType | "all">("all");
  const [authorityFilter, setAuthorityFilter] = useState<TAuthorityType | "all">("all");

  const filteredSources = useMemo(
    () =>
      sources.filter((source) => {
        if (sourceTypeFilter !== "all" && source.source_type !== sourceTypeFilter) return false;
        if (authorityFilter !== "all" && source.authority_type !== authorityFilter) return false;
        return true;
      }),
    [sources, sourceTypeFilter, authorityFilter]
  );

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="40px" />
        <Loader.Item height="240px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-tertiary" />
          <h3 className="text-14 font-semibold text-primary">{t("agent_infra.knowledge.sources")}</h3>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="text-11 text-tertiary">
            Type
            <select
              className="ml-2 rounded-md border border-subtle bg-surface-1 px-2 py-1 text-12 text-primary"
              value={sourceTypeFilter}
              onChange={(event) => setSourceTypeFilter(event.target.value as TSourceType | "all")}
            >
              <option value="all">All</option>
              {SOURCE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>

          <label className="text-11 text-tertiary">
            {t("agent_infra.knowledge.authority")}
            <select
              className="ml-2 rounded-md border border-subtle bg-surface-1 px-2 py-1 text-12 text-primary"
              value={authorityFilter}
              onChange={(event) => setAuthorityFilter(event.target.value as TAuthorityType | "all")}
            >
              <option value="all">All</option>
              {AUTHORITY_TYPES.map((authority) => (
                <option key={authority} value={authority}>
                  {authority}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {filteredSources.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <p className="text-14 font-semibold text-primary">{t("agent_infra.knowledge.no_sources")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>{t("agent_infra.knowledge.authority")}</TableHead>
                <TableHead>{t("agent_infra.knowledge.sensitivity")}</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Owner</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSources.map((source) => {
                const lifecycleStatus = getSourceLifecycleStatus(source);
                const staleness = getStalenessLevel(source);

                return (
                  <TableRow key={source.id}>
                    <TableCell>
                      <button
                        type="button"
                        className="inline-flex items-center gap-2 text-left text-13 font-medium text-primary hover:text-accent-primary"
                        onClick={() => onSourceSelect?.(source.id)}
                      >
                        <span
                          className={`h-2 w-2 shrink-0 rounded-full ${STALENESS_DOT_CLASSES[staleness]}`}
                          title={staleness}
                        />
                        {source.name}
                      </button>
                    </TableCell>
                    <TableCell className="capitalize text-13 text-secondary">{source.source_type}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${AUTHORITY_BADGE_CLASSES[source.authority_type]}`}
                      >
                        {source.authority_type}
                      </span>
                    </TableCell>
                    <TableCell className="capitalize text-13 text-secondary">{source.sensitivity}</TableCell>
                    <TableCell>
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
                    </TableCell>
                    <TableCell className="text-13 text-secondary">{source.owner ?? "—"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
