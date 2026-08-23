/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import type { TAutonomyLevel, TProjectAgentEnablement } from "@/components/agent-infra/governance-types";
import { getAgentRef } from "@/components/agent-infra/catalog-utils";
import type { AgentEntry } from "@/components/agent-infra/workforce/workforce-types";
import { useAgentEnablements } from "@/hooks/use-catalog";
import catalogService from "@/services/catalog.service";

type TEnablementPanelProps = {
  workspaceSlug: string;
  projectId: string;
  agents?: AgentEntry[];
};

const EMPTY_AGENTS: AgentEntry[] = [];
const EMPTY_ASSIGNMENT_TYPES: string[] = [];
const EMPTY_DELEGATION: string[] = [];
const AUTONOMY_LEVELS: TAutonomyLevel[] = ["supervised", "semi_autonomous", "autonomous"];

const DEFAULT_ASSIGNMENT_TYPES = ["development", "qa", "review", "deployment"];
const DEFAULT_DELEGATION = ["delegate_subtask", "read", "write"];

export function EnablementPanel(props: TEnablementPanelProps) {
  const { workspaceSlug, projectId, agents = EMPTY_AGENTS } = props;
  const { t } = useTranslation();
  const { enablements, isLoading, error, mutate } = useAgentEnablements(workspaceSlug, projectId);
  const [submittingRef, setSubmittingRef] = useState<string | null>(null);

  const enablementByRef = useMemo(() => {
    const map = new Map<string, TProjectAgentEnablement>();
    enablements?.forEach((entry) => {
      if (entry.enabled) map.set(entry.agent_ref, entry);
    });
    return map;
  }, [enablements]);

  const sortedAgents = useMemo(() => agents.toSorted((a, b) => getAgentRef(a).localeCompare(getAgentRef(b))), [agents]);

  const handleToggle = useCallback(
    async (agentRef: string, enabled: boolean) => {
      setSubmittingRef(agentRef);
      try {
        const existing = enablements?.find((entry) => entry.agent_ref === agentRef);
        if (enabled && !existing) {
          await catalogService.createEnablement(workspaceSlug, projectId, {
            agent_ref: agentRef,
            max_autonomy_level: "supervised",
            allowed_assignment_types: DEFAULT_ASSIGNMENT_TYPES,
            delegation_permissions: DEFAULT_DELEGATION,
          });
        } else if (existing) {
          if (enabled) {
            await catalogService.updateEnablement(workspaceSlug, projectId, existing.id, { enabled: true });
          } else {
            await catalogService.deleteEnablement(workspaceSlug, projectId, existing.id);
          }
        }
        await mutate();
      } finally {
        setSubmittingRef(null);
      }
    },
    [enablements, mutate, projectId, workspaceSlug]
  );

  const handleUpdate = useCallback(
    async (enablement: TProjectAgentEnablement, patch: Partial<TProjectAgentEnablement>) => {
      setSubmittingRef(enablement.agent_ref);
      try {
        await catalogService.updateEnablement(workspaceSlug, projectId, enablement.id, patch);
        await mutate();
      } finally {
        setSubmittingRef(null);
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
        <Loader.Item height="200px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.workforce.enablement_panel")}</h3>
      </div>

      {sortedAgents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.workforce.empty")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("agent_infra.workforce.agent")}</TableHead>
                <TableHead>{t("agent_infra.workforce.enabled")}</TableHead>
                <TableHead>{t("agent_infra.workforce.autonomy_level")}</TableHead>
                <TableHead>{t("agent_infra.workforce.assignment_types")}</TableHead>
                <TableHead>{t("agent_infra.workforce.delegation_permissions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedAgents.map((agent) => {
                const agentRef = getAgentRef(agent);
                const enablement = enablementByRef.get(agentRef);
                const isEnabled = Boolean(enablement);
                const isSubmitting = submittingRef === agentRef;
                const assignmentTypes = enablement?.allowed_assignment_types ?? EMPTY_ASSIGNMENT_TYPES;
                const assignmentSet = new Set(assignmentTypes);
                const delegation = enablement?.delegation_permissions ?? EMPTY_DELEGATION;
                const delegationSet = new Set(delegation);

                return (
                  <TableRow key={agent.path}>
                    <TableCell className="text-13 font-medium text-primary">{agentRef}</TableCell>
                    <TableCell>
                      <label className="inline-flex items-center gap-2 text-13">
                        <input
                          type="checkbox"
                          checked={isEnabled}
                          disabled={isSubmitting}
                          onChange={(event) => handleToggle(agentRef, event.target.checked)}
                        />
                        {isEnabled ? t("agent_infra.workforce.enabled_yes") : t("agent_infra.workforce.enabled_no")}
                      </label>
                    </TableCell>
                    <TableCell>
                      <select
                        aria-label={t("agent_infra.workforce.autonomy_level")}
                        className="rounded-md border border-subtle bg-surface-1 px-2 py-1 text-12 text-primary"
                        value={enablement?.max_autonomy_level ?? "supervised"}
                        disabled={!isEnabled || isSubmitting}
                        onChange={(event) =>
                          enablement &&
                          handleUpdate(enablement, {
                            max_autonomy_level: event.target.value as TAutonomyLevel,
                          })
                        }
                      >
                        {AUTONOMY_LEVELS.map((level) => (
                          <option key={level} value={level}>
                            {t(`agent_infra.workforce.autonomy.${level}`)}
                          </option>
                        ))}
                      </select>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        {DEFAULT_ASSIGNMENT_TYPES.map((type) => (
                          <label key={type} className="inline-flex items-center gap-1 text-11 text-secondary">
                            <input
                              type="checkbox"
                              checked={assignmentSet.has(type)}
                              disabled={!isEnabled || isSubmitting}
                              onChange={(event) => {
                                if (!enablement) return;
                                const next = event.target.checked
                                  ? [...assignmentTypes, type]
                                  : assignmentTypes.filter((item) => item !== type);
                                handleUpdate(enablement, { allowed_assignment_types: next });
                              }}
                            />
                            {type}
                          </label>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        {DEFAULT_DELEGATION.map((permission) => (
                          <label key={permission} className="inline-flex items-center gap-1 text-11 text-secondary">
                            <input
                              type="checkbox"
                              checked={delegationSet.has(permission)}
                              disabled={!isEnabled || isSubmitting}
                              onChange={(event) => {
                                if (!enablement) return;
                                const next = event.target.checked
                                  ? [...delegation, permission]
                                  : delegation.filter((item) => item !== permission);
                                handleUpdate(enablement, { delegation_permissions: next });
                              }}
                            />
                            {permission}
                          </label>
                        ))}
                      </div>
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
