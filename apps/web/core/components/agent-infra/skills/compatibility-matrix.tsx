/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Grid3X3 } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { getAgentRef } from "@/components/agent-infra/catalog-utils";
import type { AgentEntry } from "@/components/agent-infra/workforce/workforce-types";
import type { SkillEntry } from "./skills-types";

type TCompatibilityMatrixProps = {
  skills?: SkillEntry[];
  agents?: AgentEntry[];
};

const EMPTY_SKILLS: SkillEntry[] = [];
const EMPTY_AGENTS: AgentEntry[] = [];

export function CompatibilityMatrix(props: TCompatibilityMatrixProps) {
  const { skills = EMPTY_SKILLS, agents = EMPTY_AGENTS } = props;
  const { t } = useTranslation();

  const matrix = useMemo(() => {
    return skills.map((skill) => {
      const skillName = skill.name ?? skill.path;
      const usingAgents = agents.filter((agent) =>
        (agent.skills ?? []).some((item) => item === skillName || item.includes(skillName))
      );
      const compatible = skill.status === "ok" && usingAgents.every((agent) => agent.status === "ok");

      return {
        skill,
        skillName,
        usingAgents,
        compatible,
      };
    });
  }, [agents, skills]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Grid3X3 className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.skills.compatibility_matrix")}</h3>
      </div>

      {matrix.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.skills.compatibility_empty")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("agent_infra.skills.skill")}</TableHead>
                <TableHead>{t("agent_infra.skills.used_by_agents")}</TableHead>
                <TableHead>{t("agent_infra.skills.compatibility_status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matrix.map(({ skill, skillName, usingAgents, compatible }) => (
                <TableRow key={skill.path}>
                  <TableCell className="text-13 font-medium text-primary">{skillName}</TableCell>
                  <TableCell className="text-13 text-secondary">
                    {usingAgents.length > 0
                      ? usingAgents.map((agent) => getAgentRef(agent)).join(", ")
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={compatible ? "accent-success" : "accent-warning"} size="sm" disabled>
                      {compatible
                        ? t("agent_infra.skills.compatible")
                        : t("agent_infra.skills.needs_attention")}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
