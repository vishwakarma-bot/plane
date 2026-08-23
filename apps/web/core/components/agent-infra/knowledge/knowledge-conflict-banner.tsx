/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TKnowledgeConflict } from "./knowledge-types";

type TKnowledgeConflictBannerProps = {
  conflict: TKnowledgeConflict;
  onCompareVersion?: (sourceId: string, versionId: string) => void;
};

export function KnowledgeConflictBanner(props: TKnowledgeConflictBannerProps) {
  const { conflict, onCompareVersion } = props;
  const { t } = useTranslation();
  const [firstVersion, secondVersion] = conflict.approvedVersions;

  if (!firstVersion || !secondVersion) return null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-950/30">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
        <div className="min-w-0 flex-1">
          <p className="text-14 font-semibold text-amber-900 dark:text-amber-100">
            {conflict.approvedVersions.length} approved versions for source {conflict.sourceName} — resolve
            conflict
          </p>
          <p className="mt-1 text-13 text-amber-800 dark:text-amber-200">
            {t("agent_infra.knowledge.conflicts")}
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              type="button"
              className="text-13 font-medium text-accent-primary hover:underline"
              onClick={() => onCompareVersion?.(conflict.sourceId, firstVersion.id)}
            >
              Compare v{firstVersion.version_number}
            </button>
            <button
              type="button"
              className="text-13 font-medium text-accent-primary hover:underline"
              onClick={() => onCompareVersion?.(conflict.sourceId, secondVersion.id)}
            >
              Compare v{secondVersion.version_number}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
