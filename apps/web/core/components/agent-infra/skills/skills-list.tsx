/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { Sparkles } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Badge, Loader } from "@plane/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import { CATALOG_STATUS_BADGE_CLASSES } from "../catalog-utils";
import type { SkillEntry } from "../workforce/workforce-types";

type TSkillsListProps = {
  skills?: SkillEntry[];
  isLoading?: boolean;
  selectedPath?: string | null;
  onSkillSelect?: (path: string) => void;
};

const EMPTY_SKILLS: SkillEntry[] = [];

export function SkillsList(props: TSkillsListProps) {
  const { skills = EMPTY_SKILLS, isLoading = false, selectedPath, onSkillSelect } = props;
  const { t } = useTranslation();

  const sortedSkills = useMemo(
    () =>
      // oxlint-disable-next-line unicorn/no-array-sort -- ES2022 target lacks Array#toSorted()
      [...skills].sort((left: SkillEntry, right: SkillEntry) =>
        (left.name ?? left.path).localeCompare(right.name ?? right.path)
      ),
    [skills]
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
        <Sparkles className="h-4 w-4 text-tertiary" />
        <h3 className="text-14 font-semibold text-primary">{t("agent_infra.skills_tab.title")}</h3>
      </div>

      {sortedSkills.length === 0 ? (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <p className="text-14 font-semibold text-primary">{t("agent_infra.skills_tab.empty")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-subtle">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>{t("agent_infra.skills_tab.type_label")}</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>{t("agent_infra.skills_tab.summary_label")}</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedSkills.map((skill) => {
                const isSelected = selectedPath === skill.path;
                const hasValidationErrors = (skill.validation_errors?.length ?? 0) > 0;

                return (
                  <TableRow key={skill.path}>
                    <TableCell>
                      <button
                        type="button"
                        className={`text-left text-13 font-medium hover:text-accent-primary ${
                          isSelected ? "text-accent-primary" : "text-primary"
                        }`}
                        onClick={() => onSkillSelect?.(skill.path)}
                      >
                        {skill.name ?? skill.path}
                      </button>
                    </TableCell>
                    <TableCell className="text-13 text-secondary capitalize">{skill.type ?? "—"}</TableCell>
                    <TableCell className="max-w-xs truncate text-13 text-secondary">
                      {skill.description ?? "—"}
                    </TableCell>
                    <TableCell className="max-w-sm truncate text-13 text-secondary">{skill.summary ?? "—"}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span
                          className={`inline-flex rounded-sm px-1.5 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[skill.status]}`}
                        >
                          {skill.status}
                        </span>
                        {hasValidationErrors && (
                          <Badge variant="accent-warning" size="sm" disabled>
                            {skill.validation_errors?.length} warning
                            {(skill.validation_errors?.length ?? 0) === 1 ? "" : "s"}
                          </Badge>
                        )}
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
