/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { Loader } from "@plane/ui";
import { useCatalogSkills } from "@/hooks/use-catalog";
import { SkillsDetail } from "./skills-detail";
import { SkillsList } from "./skills-list";

type TSkillsSectionProps = {
  workspaceSlug: string;
  projectId: string;
};

export function SkillsSection(props: TSkillsSectionProps) {
  const { workspaceSlug, projectId } = props;
  const { t } = useTranslation();
  const { skills, isLoading, error } = useCatalogSkills(workspaceSlug, projectId);
  const defaultPath = skills?.[0]?.path ?? null;
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const activePath = selectedPath ?? defaultPath;

  const selectedSkill = useMemo(
    () => skills?.find((skill) => skill.path === activePath),
    [skills, activePath]
  );

  if (error) {
    return (
      <div className="grid place-items-center rounded-lg border border-subtle bg-surface-1 px-6 py-16">
        <EmptyStateDetailed
          title={t("agent_infra.error_state.title")}
          description={t("agent_infra.error_state.description")}
          assetKey="project"
          assetClassName="size-32"
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <Loader className="space-y-4">
        <Loader.Item height="48px" />
        <Loader.Item height="280px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <SkillsList skills={skills} selectedPath={activePath} onSkillSelect={setSelectedPath} />
      {selectedSkill && <SkillsDetail skill={selectedSkill} />}
    </div>
  );
}
