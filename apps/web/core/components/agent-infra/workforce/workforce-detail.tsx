/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { CATALOG_STATUS_BADGE_CLASSES, truncateContentHash } from "../catalog-utils";
import type { AgentEntry } from "./workforce-types";

type TWorkforceDetailProps = {
  agent: AgentEntry;
};

function renderListItems(items?: string[]) {
  if (!items || items.length === 0) {
    return <p className="text-13 text-tertiary">—</p>;
  }

  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <li
          key={item}
          className="rounded-sm bg-layer-2 px-2 py-0.5 text-12 text-secondary"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

export function WorkforceDetail(props: TWorkforceDetailProps) {
  const { agent } = props;
  const { t } = useTranslation();

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-16 font-semibold text-primary">{t("agent_infra.workforce.agent_details")}</h3>
          <p className="mt-1 text-13 text-secondary">{agent.name ?? agent.path}</p>
        </div>
        <span
          className={`inline-flex rounded-sm px-2 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[agent.status]}`}
        >
          {agent.status}
        </span>
      </div>

      {agent.description && <p className="mt-4 text-13 text-secondary">{agent.description}</p>}

      {(agent.validation_errors?.length ?? 0) > 0 && (
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-950/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <ul className="space-y-1 text-13 text-amber-900 dark:text-amber-100">
            {agent.validation_errors?.map((validationError) => (
              <li key={validationError}>{validationError}</li>
            ))}
          </ul>
        </div>
      )}

      <dl className="mt-6 grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">
            {t("agent_infra.workforce.model_preference")}
          </dt>
          <dd className="mt-1 text-13 text-primary">{agent.model_preference ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">Path</dt>
          <dd className="mt-1 font-mono text-12 text-secondary">{agent.path}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium uppercase tracking-wide text-tertiary">Content Hash</dt>
          <dd className="mt-1 font-mono text-12 text-secondary">{truncateContentHash(agent.content_hash)}</dd>
        </div>
      </dl>

      <div className="mt-6 space-y-4">
        <div>
          <h4 className="text-13 font-semibold text-primary">{t("agent_infra.workforce.assignment_types")}</h4>
          <div className="mt-2">{renderListItems(agent.assignment_types)}</div>
        </div>
        <div>
          <h4 className="text-13 font-semibold text-primary">{t("agent_infra.workforce.skills_label")}</h4>
          <div className="mt-2">{renderListItems(agent.skills)}</div>
        </div>
      </div>
    </div>
  );
}
