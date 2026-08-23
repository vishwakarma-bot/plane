/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { ArrowRight, GitBranch } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { AUTHORIZING_AGENT_REF, getAgentRef } from "@/components/agent-infra/catalog-utils";
import type { AgentEntry } from "./workforce-types";

type TValidationChainProps = {
  agents?: AgentEntry[];
};

const EMPTY_AGENTS: AgentEntry[] = [];

export function ValidationChain(props: TValidationChainProps) {
  const { agents = EMPTY_AGENTS } = props;
  const { t } = useTranslation();

  const chain = useMemo(
    () =>
      [...agents]
        .map((agent) => {
          const agentRef = getAgentRef(agent);
          const authorizingAgent =
            agent.authorizing_agent ??
            (agent.constraints?.require_review_before_merge ? AUTHORIZING_AGENT_REF : AUTHORIZING_AGENT_REF);
          return { agentRef, authorizingAgent };
        })
        .sort((a, b) => a.agentRef.localeCompare(b.agentRef)),
    [agents]
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.workforce.validation_chain")}</h3>
      </div>

      {chain.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.workforce.validation_chain_empty")}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {chain.map(({ agentRef, authorizingAgent }) => (
            <div
              key={agentRef}
              className="flex items-center gap-3 rounded-lg border border-subtle bg-surface-1 px-4 py-3"
            >
              <span className="text-13 font-medium text-primary">{agentRef}</span>
              <ArrowRight className="h-3.5 w-3.5 shrink-0 text-tertiary" />
              <span className="text-13 text-secondary">{authorizingAgent}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
