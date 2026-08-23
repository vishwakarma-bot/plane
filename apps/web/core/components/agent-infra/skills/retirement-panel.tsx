/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Archive } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/ui";
import type { SkillEntry } from "./skills-types";

type TRetirementPanelProps = {
  skills?: SkillEntry[];
};

const EMPTY_SKILLS: SkillEntry[] = [];

export function RetirementPanel(props: TRetirementPanelProps) {
  const { skills = EMPTY_SKILLS } = props;
  const { t } = useTranslation();

  const retiredSkills = useMemo(
    () =>
      skills.filter(
        (skill) =>
          skill.lifecycle_status === "deprecated" ||
          skill.lifecycle_status === "retired" ||
          skill.status === "error"
      ),
    [skills]
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Archive className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.skills.retirement")}</h3>
      </div>

      {retiredSkills.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-8 text-center text-13 text-tertiary">
          {t("agent_infra.skills.retirement_empty")}
        </div>
      ) : (
        <div className="space-y-2">
          {retiredSkills.map((skill) => (
            <div
              key={skill.path}
              className="flex items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3"
            >
              <div>
                <p className="text-13 font-medium text-primary">{skill.name ?? skill.path}</p>
                <p className="mt-0.5 font-mono text-11 text-tertiary">{skill.path}</p>
              </div>
              <Badge variant="accent-warning" size="sm" disabled>
                {skill.lifecycle_status ?? skill.status}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
