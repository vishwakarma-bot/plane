/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Plug } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { CATALOG_STATUS_BADGE_CLASSES, safeStringList, truncateContentHash } from "../catalog-utils";
import type { IntegrationEntry } from "../workforce/workforce-types";

type TIntegrationsListProps = {
  integrations?: IntegrationEntry[];
  isLoading?: boolean;
};

const EMPTY_INTEGRATIONS: IntegrationEntry[] = [];

function getIntegrationStatusClass(status: IntegrationEntry["status"]): string {
  if (status in CATALOG_STATUS_BADGE_CLASSES) {
    return CATALOG_STATUS_BADGE_CLASSES[status as keyof typeof CATALOG_STATUS_BADGE_CLASSES];
  }
  return CATALOG_STATUS_BADGE_CLASSES.disabled;
}

export function IntegrationsList(props: TIntegrationsListProps) {
  const { integrations = EMPTY_INTEGRATIONS, isLoading = false } = props;
  const { t } = useTranslation();

  const sortedIntegrations = useMemo(
    () =>
      [...integrations].toSorted((left: IntegrationEntry, right: IntegrationEntry) =>
        (left.name ?? left.path).localeCompare(right.name ?? right.path)
      ),
    [integrations]
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
        <Plug className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.integrations_tab.title")}</h3>
      </div>

      {sortedIntegrations.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <p className="text-14 font-semibold text-primary">{t("agent_infra.integrations_tab.empty")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>{t("agent_infra.integrations_tab.type")}</TableHead>
                <TableHead>{t("agent_infra.integrations_tab.tools")}</TableHead>
                <TableHead>{t("agent_infra.integrations_tab.scopes")}</TableHead>
                <TableHead>{t("agent_infra.integrations_tab.approval_class")}</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedIntegrations.map((integration) => {
                const hasValidationErrors = (integration.validation_errors?.length ?? 0) > 0;

                return (
                  <TableRow key={integration.path}>
                    <TableCell className="text-13 font-medium text-primary">
                      {integration.name ?? integration.path}
                    </TableCell>
                    <TableCell className="text-13 text-secondary uppercase">{integration.type ?? "—"}</TableCell>
                    <TableCell className="max-w-xs truncate text-13 text-secondary">
                      {safeStringList(integration.tools).join(", ") || "—"}
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-13 text-secondary">
                      {safeStringList(integration.scopes).join(", ") || "—"}
                    </TableCell>
                    <TableCell className="text-13 text-secondary">{integration.approval_class ?? "—"}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span
                          className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${getIntegrationStatusClass(integration.status)}`}
                        >
                          {integration.status}
                        </span>
                        {hasValidationErrors && (
                          <Badge variant="accent-warning" size="sm" disabled>
                            {integration.validation_errors?.length} warning
                            {(integration.validation_errors?.length ?? 0) === 1 ? "" : "s"}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-12 text-tertiary">
                      {truncateContentHash(integration.content_hash)}
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
