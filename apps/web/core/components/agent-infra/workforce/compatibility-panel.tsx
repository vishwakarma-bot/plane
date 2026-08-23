/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Link2, XCircle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Loader } from "@plane/ui";
import { getAgentRef } from "@/components/agent-infra/catalog-utils";
import type { TCompatibilityRecord } from "@/components/agent-infra/governance-types";
import catalogService from "@/services/catalog.service";
import type { AgentEntry } from "./workforce-types";

type TCompatibilityPanelProps = {
  workspaceSlug: string;
  projectId: string;
  agent?: AgentEntry;
};

type TCompatibilityRow = TCompatibilityRecord & { label: string };

const EMPTY_ROWS: TCompatibilityRow[] = [];

export function CompatibilityPanel(props: TCompatibilityPanelProps) {
  const { workspaceSlug, projectId, agent } = props;
  const { t } = useTranslation();
  const [rows, setRows] = useState<TCompatibilityRow[]>(EMPTY_ROWS);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const checks = useMemo(() => {
    if (!agent) return [];
    const agentRef = getAgentRef(agent);
    const targets: Array<{ target_type: string; target_ref: string; label: string }> = [];

    agent.skills?.forEach((skill) => {
      targets.push({ target_type: "skill", target_ref: skill, label: `skill:${skill}` });
    });

    if (agent.model_preference) {
      targets.push({
        target_type: "model",
        target_ref: agent.model_preference,
        label: `model:${agent.model_preference}`,
      });
    }

    agent.fallback_models?.forEach((model) => {
      targets.push({ target_type: "model", target_ref: model, label: `model:${model}` });
    });

    return targets.map((target) => ({
      ...target,
      source_type: "agent",
      source_ref: agentRef,
    }));
  }, [agent]);

  useEffect(() => {
    if (!agent || checks.length === 0) {
      setRows(EMPTY_ROWS);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    Promise.all(
      checks.map((check) =>
        catalogService
          .checkCompatibility(workspaceSlug, projectId, {
            source_type: check.source_type,
            source_ref: check.source_ref,
            target_type: check.target_type,
            target_ref: check.target_ref,
          })
          .then((record) => ({ ...record, label: check.label }))
      )
    )
      .then((results) => {
        if (!cancelled) setRows(results);
      })
      .catch((fetchError) => {
        if (!cancelled) setError(fetchError);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [agent, checks, projectId, workspaceSlug]);

  if (!agent) {
    return (
      <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-4 py-6 text-center text-13 text-tertiary">
        {t("agent_infra.workforce.compatibility_select_agent")}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Link2 className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.workforce.compatibility")}</h3>
      </div>

      {error ? (
        <div className="rounded-lg border border-subtle bg-surface-1 px-4 py-6 text-center text-13 text-tertiary">
          {t("agent_infra.error_state.description")}
        </div>
      ) : isLoading ? (
        <Loader className="space-y-2">
          <Loader.Item height="40px" />
          <Loader.Item height="40px" />
        </Loader>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-4 py-6 text-center text-13 text-tertiary">
          {t("agent_infra.workforce.compatibility_empty")}
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <div
              key={`${row.target_type}-${row.target_ref}`}
              className="flex items-start justify-between gap-3 rounded-lg border border-subtle bg-surface-1 px-4 py-3"
            >
              <div>
                <p className="text-13 font-medium text-primary">{row.label}</p>
                {row.reason && <p className="mt-1 text-12 text-secondary">{row.reason}</p>}
              </div>
              <span className="inline-flex items-center gap-1 text-12 font-medium">
                {row.compatible ? (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                    <span className="text-green-700 dark:text-green-300">
                      {t("agent_infra.workforce.compatible")}
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-3.5 w-3.5 text-red-600" />
                    <span className="text-red-700 dark:text-red-300">
                      {t("agent_infra.workforce.incompatible")}
                    </span>
                  </>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
