/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { CheckCircle, RotateCcw, XCircle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TCatalogRevision } from "@/components/agent-infra/governance-types";
import catalogService from "@/services/catalog.service";

type TCatalogRevisionActionsProps = {
  workspaceSlug: string;
  projectId: string;
  revision: TCatalogRevision;
  onActionComplete?: () => Promise<void> | void;
};

export function CatalogRevisionActions(props: TCatalogRevisionActionsProps) {
  const { workspaceSlug, projectId, revision, onActionComplete } = props;
  const { t } = useTranslation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const runAction = useCallback(
    async (action: () => Promise<unknown>) => {
      setIsSubmitting(true);
      try {
        await action();
        await onActionComplete?.();
      } finally {
        setIsSubmitting(false);
      }
    },
    [onActionComplete]
  );

  if (revision.status === "pending_approval") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="primary"
          size="xs"
          disabled={isSubmitting}
          onClick={() =>
            runAction(() => catalogService.approveCatalogRevision(workspaceSlug, projectId, revision.id))
          }
        >
          <CheckCircle className="mr-1 h-3 w-3" />
          {t("agent_infra.governance.approve")}
        </Button>
        <input
          type="text"
          value={rejectReason}
          onChange={(event) => setRejectReason(event.target.value)}
          placeholder={t("agent_infra.governance.reject_reason_placeholder")}
          className="min-w-[160px] rounded-md border border-subtle bg-surface-1 px-2 py-1 text-12 text-primary"
        />
        <Button
          variant="outline-neutral"
          size="xs"
          disabled={isSubmitting}
          onClick={() =>
            runAction(() =>
              catalogService.rejectCatalogRevision(workspaceSlug, projectId, revision.id, rejectReason)
            )
          }
          className="text-red-600 hover:text-red-700"
        >
          <XCircle className="mr-1 h-3 w-3" />
          {t("agent_infra.governance.reject")}
        </Button>
      </div>
    );
  }

  if (revision.status === "approved") {
    return (
      <Button
        variant="outline-neutral"
        size="xs"
        disabled={isSubmitting}
        onClick={() =>
          runAction(() => catalogService.rollbackCatalogRevision(workspaceSlug, projectId, revision.id))
        }
      >
        <RotateCcw className="mr-1 h-3 w-3" />
        {t("agent_infra.governance.rollback")}
      </Button>
    );
  }

  return null;
}
