/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { CATALOG_STATUS_BADGE_CLASSES, truncateContentHash } from "../catalog-utils";
import type { SkillEntry } from "../workforce/workforce-types";

type TSkillsDetailProps = {
  skill: SkillEntry;
};

export function SkillsDetail(props: TSkillsDetailProps) {
  const { skill } = props;
  const { t } = useTranslation();

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-16 font-semibold text-primary">{t("agent_infra.skills_tab.skill_details")}</h3>
          <p className="mt-1 text-13 text-secondary">{skill.name ?? skill.path}</p>
        </div>
        <span
          className={`inline-flex rounded-sm px-2 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[skill.status]}`}
        >
          {skill.status}
        </span>
      </div>

      {(skill.validation_errors?.length ?? 0) > 0 && (
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-950/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <ul className="space-y-1 text-13 text-amber-900 dark:text-amber-100">
            {skill.validation_errors?.map((validationError) => (
              <li key={validationError}>{validationError}</li>
            ))}
          </ul>
        </div>
      )}

      <dl className="mt-6 grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">
            {t("agent_infra.skills_tab.type_label")}
          </dt>
          <dd className="mt-1 capitalize text-13 text-primary">{skill.type ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">Path</dt>
          <dd className="mt-1 font-mono text-12 text-secondary">{skill.path}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">Content Hash</dt>
          <dd className="mt-1 font-mono text-12 text-secondary">{truncateContentHash(skill.content_hash)}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">Description</dt>
          <dd className="mt-1 text-13 text-secondary">{skill.description ?? "—"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">
            {t("agent_infra.skills_tab.summary_label")}
          </dt>
          <dd className="mt-1 text-13 text-secondary">{skill.summary ?? "—"}</dd>
        </div>
      </dl>
    </div>
  );
}
