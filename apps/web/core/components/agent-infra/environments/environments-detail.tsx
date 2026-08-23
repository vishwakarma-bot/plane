/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { CATALOG_STATUS_BADGE_CLASSES, truncateContentHash } from "../catalog-utils";
import type { EnvironmentEntry } from "../workforce/workforce-types";

type TEnvironmentsDetailProps = {
  environment: EnvironmentEntry;
};

function renderListItems(items?: string[]) {
  if (!items || items.length === 0) {
    return <p className="text-13 text-tertiary">—</p>;
  }

  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li key={item} className="font-mono rounded-sm bg-layer-2 px-3 py-1.5 text-12 text-secondary">
          {item}
        </li>
      ))}
    </ul>
  );
}

export function EnvironmentsDetail(props: TEnvironmentsDetailProps) {
  const { environment } = props;
  const { t } = useTranslation();

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-16 font-semibold text-primary">{environment.name ?? environment.path}</h3>
          {environment.description && <p className="mt-1 text-13 text-secondary">{environment.description}</p>}
        </div>
        <span
          className={`inline-flex rounded-sm px-2 py-0.5 text-11 font-medium capitalize ${CATALOG_STATUS_BADGE_CLASSES[environment.status]}`}
        >
          {environment.status}
        </span>
      </div>

      {(environment.validation_errors?.length ?? 0) > 0 && (
        <div className="border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/30 mt-4 flex items-start gap-3 rounded-lg border px-4 py-3">
          <AlertTriangle className="text-amber-600 mt-0.5 h-4 w-4 shrink-0" />
          <ul className="text-amber-900 dark:text-amber-100 space-y-1 text-13">
            {environment.validation_errors?.map((validationError) => (
              <li key={validationError}>{validationError}</li>
            ))}
          </ul>
        </div>
      )}

      <dl className="mt-6 grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Path</dt>
          <dd className="font-mono mt-1 text-12 text-secondary">{environment.path}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">
            {t("agent_infra.environments_tab.snapshot")}
          </dt>
          <dd className="font-mono mt-1 text-12 text-secondary">{truncateContentHash(environment.content_hash)}</dd>
        </div>
      </dl>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div>
          <h4 className="text-13 font-semibold text-primary">{t("agent_infra.environments_tab.toolchain")}</h4>
          <div className="mt-2">{renderListItems(environment.toolchain)}</div>
        </div>
        <div>
          <h4 className="text-13 font-semibold text-primary">{t("agent_infra.environments_tab.capabilities")}</h4>
          <div className="mt-2">{renderListItems(environment.capabilities)}</div>
        </div>
      </div>
    </div>
  );
}
