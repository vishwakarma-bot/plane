/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import type { ElementType } from "react";
import { Cloud, GitBranch, Network, Plug, Rocket } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { formatUtcTimestamp, HEALTH_STATUS_CLASSES, parseUsd } from "@/components/agent-infra/catalog-utils";
import type { TIntegrationRegistration, TIntegrationType } from "@/components/agent-infra/governance-types";
import { useIntegrationRegistrations } from "@/hooks/use-catalog";

type TRegistrationsPanelProps = {
  workspaceSlug: string;
  projectId: string;
};

const EMPTY_REGISTRATIONS: TIntegrationRegistration[] = [];

const TYPE_ICONS: Record<TIntegrationType, ElementType> = {
  mcp: Network,
  a2a: Cloud,
  git_ci: GitBranch,
  deployment: Rocket,
};

function getApprovalBadgeVariant(approvalClass: string) {
  if (approvalClass === "restricted") return "accent-destructive" as const;
  if (approvalClass === "manual") return "accent-warning" as const;
  return "accent-success" as const;
}

export function RegistrationsPanel(props: TRegistrationsPanelProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { registrations, isLoading, error } = useIntegrationRegistrations(workspaceSlug, projectId);

  const sorted = useMemo(
    () =>
      // oxlint-disable-next-line unicorn/no-array-sort -- ES2022 target lacks Array#toSorted()
      (registrations ?? EMPTY_REGISTRATIONS).toSorted((a: TIntegrationRegistration, b: TIntegrationRegistration) =>
        a.integration_ref.localeCompare(b.integration_ref)
      ),
    [registrations]
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
        <Loader.Item height="200px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Plug className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.integrations.registrations_panel")}</h3>
      </div>

      {sorted.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.integrations.registrations_empty")}
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {sorted.map((registration) => {
            const Icon = TYPE_ICONS[registration.integration_type] ?? Plug;
            const failureRate = parseUsd(registration.failure_rate_percent);

            return (
              <div key={registration.id} className="rounded-lg border border-subtle bg-surface-1 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-tertiary" />
                    <div>
                      <p className="text-14 font-semibold text-primary">{registration.integration_ref}</p>
                      <p className="text-11 text-tertiary uppercase">{registration.integration_type}</p>
                    </div>
                  </div>
                  <span
                    className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${HEALTH_STATUS_CLASSES[registration.health_status] ?? HEALTH_STATUS_CLASSES.unknown}`}
                  >
                    {registration.health_status}
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Badge variant="outline-neutral" size="sm" disabled>
                    {registration.status}
                  </Badge>
                  <Badge variant={getApprovalBadgeVariant(registration.approval_class)} size="sm" disabled>
                    {t("agent_infra.integrations.approval_class")}: {registration.approval_class}
                  </Badge>
                </div>

                <dl className="mt-4 space-y-3 text-13">
                  <div>
                    <dt className="text-11 text-tertiary uppercase">{t("agent_infra.integrations.granted_agents")}</dt>
                    <dd className="mt-1 text-secondary">
                      {registration.granted_agents.length > 0 ? registration.granted_agents.join(", ") : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-11 text-tertiary uppercase">{t("agent_infra.integrations.scopes")}</dt>
                    <dd className="mt-1 text-secondary">
                      {registration.granted_scopes.length > 0 ? registration.granted_scopes.join(", ") : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-11 text-tertiary uppercase">{t("agent_infra.integrations.failure_rate")}</dt>
                    <dd className="mt-2">
                      <div className="h-2 overflow-hidden rounded-full bg-layer-2">
                        <div
                          className={`h-full rounded-full ${failureRate >= 10 ? "bg-red-500" : failureRate >= 5 ? "bg-amber-500" : "bg-green-500"}`}
                          style={{ width: `${Math.min(100, failureRate)}%` }}
                        />
                      </div>
                      <p className="mt-1 text-11 text-tertiary">{failureRate.toFixed(2)}%</p>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-11 text-tertiary uppercase">
                      {t("agent_infra.integrations.last_health_check")}
                    </dt>
                    <dd className="mt-1 text-secondary">{formatUtcTimestamp(registration.last_health_check_at)}</dd>
                  </div>
                </dl>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
