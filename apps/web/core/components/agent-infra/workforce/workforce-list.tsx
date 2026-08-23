/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Bot } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { CATALOG_STATUS_BADGE_CLASSES, truncateContentHash } from "../catalog-utils";
import type { AgentEntry } from "./workforce-types";

type TWorkforceListProps = {
  agents?: AgentEntry[];
  isLoading?: boolean;
  selectedPath?: string | null;
  onAgentSelect?: (path: string) => void;
};

const EMPTY_AGENTS: AgentEntry[] = [];

export function WorkforceList(props: TWorkforceListProps) {
  const { agents = EMPTY_AGENTS, isLoading = false, selectedPath, onAgentSelect } = props;
  const { t } = useTranslation();

  const sortedAgents = useMemo(
    () => agents.toSorted((left, right) => (left.name ?? left.path).localeCompare(right.name ?? right.path)),
    [agents]
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
      <div className="flex items-center gap-2">
        <Bot className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.workforce.title")}</h3>
      </div>

      {sortedAgents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <p className="text-14 font-semibold text-primary">{t("agent_infra.workforce.empty")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>{t("agent_infra.workforce.model_preference")}</TableHead>
                <TableHead>{t("agent_infra.workforce.skills_label")}</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedAgents.map((agent) => {
                const isSelected = selectedPath === agent.path;
                const hasValidationErrors = (agent.validation_errors?.length ?? 0) > 0;

                return (
                  <TableRow key={agent.path}>
                    <TableCell>
                      <button
                        type="button"
                        className={`text-left text-13 font-medium hover:text-accent-primary ${
                          isSelected ? "text-accent-primary" : "text-primary"
                        }`}
                        onClick={() => onAgentSelect?.(agent.path)}
                      >
                        {agent.name ?? agent.path}
                      </button>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-13 text-secondary">
                      {agent.description ?? "—"}
                    </TableCell>
                    <TableCell className="text-13 text-secondary">{agent.model_preference ?? "—"}</TableCell>
                    <TableCell className="text-13 text-secondary">
                      {(agent.skills ?? []).join(", ") || "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span
                          className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[agent.status]}`}
                        >
                          {agent.status}
                        </span>
                        {hasValidationErrors && (
                          <Badge variant="accent-warning" size="sm" disabled>
                            {agent.validation_errors?.length} warning
                            {(agent.validation_errors?.length ?? 0) === 1 ? "" : "s"}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-12 text-tertiary">
                      {truncateContentHash(agent.content_hash)}
                    </TableCell>
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
