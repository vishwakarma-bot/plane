/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */
import type { ReactNode } from "react";
import { useMemo } from "react";
import { useSWRConfig } from "swr";
import { Download, FileText, X } from "lucide-react";
import type { TBadgeVariant } from "@plane/ui";
import { Badge, Button, Loader } from "@plane/ui";
import { useAgentRunDetail } from "@/hooks/use-agent-infra";
import { DispositionAction } from "./disposition-action";
import type { TProgressionOutcome, TRunOutcome } from "./mock-data";
import {
  DISPOSITION_STATUS_LABELS,
  PROGRESSION_OUTCOME_LABELS,
  RUN_OUTCOME_LABELS,
  formatCost,
  formatDuration,
  formatRelativeTime,
  formatTokenCount,
} from "./mock-data";
import { ReviewBadge } from "./review-badge";

type TRunDetailProps = {
  workspaceSlug: string;
  projectId: string;
  runId: string;
  onClose?: () => void;
};

const OUTCOME_VARIANTS: Record<TRunOutcome, TBadgeVariant> = {
  success: "accent-success",
  failure: "accent-destructive",
  partial: "accent-warning",
};

const PROGRESSION_VARIANTS: Record<TProgressionOutcome, TBadgeVariant> = {
  auto_progress: "accent-success",
  awaiting_disposition: "accent-warning",
  blocked: "accent-destructive",
};

export function RunDetail(props: TRunDetailProps) {
  const { workspaceSlug, projectId, runId, onClose } = props;
  const { mutate: globalMutate } = useSWRConfig();
  const { runDetail, isLoading, error, mutate } = useAgentRunDetail(workspaceSlug, projectId, runId);
  const now = useMemo(() => new Date(), []);

  if (isLoading) {
    return (
      <div className="flex h-full flex-col">
        <RunDetailHeader onClose={onClose} />
        <div className="flex-1 p-6">
          <Loader className="space-y-4">
            <Loader.Item height="80px" />
            <Loader.Item height="120px" />
            <Loader.Item height="120px" />
          </Loader>
        </div>
      </div>
    );
  }

  if (error || !runDetail) {
    return (
      <div className="flex h-full flex-col">
        <RunDetailHeader onClose={onClose} />
        <div className="flex flex-1 items-center justify-center p-6">
          <p className="text-13 text-tertiary">Unable to load run details.</p>
        </div>
      </div>
    );
  }

  const durationMs =
    runDetail.completedAt && runDetail.startedAt
      ? new Date(runDetail.completedAt).getTime() - new Date(runDetail.startedAt).getTime()
      : 0;
  const needsDisposition =
    runDetail.review &&
    (runDetail.review.verdict === "flagged" || runDetail.review.verdict === "escalated") &&
    !runDetail.disposition;

  return (
    <div className="flex h-full flex-col">
      <RunDetailHeader agentRef={runDetail.agentRef} onClose={onClose} />

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        <section className="rounded-lg border border-subtle bg-surface-1 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={OUTCOME_VARIANTS[runDetail.outcome]} size="sm" disabled>
              {RUN_OUTCOME_LABELS[runDetail.outcome]}
            </Badge>
            <span className="text-13 font-medium text-primary">{runDetail.modelUsed}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-6">
            <DetailMetric label="Duration" value={formatDuration(Math.max(durationMs, 0))} />
            <DetailMetric label="Cost" value={formatCost(runDetail.costUsd)} />
            <DetailMetric label="Agent" value={runDetail.agentRef} />
          </div>
        </section>

        <LayerSection title="Layer 1: Execution Outcome">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <DetailMetric label="Started" value={formatRelativeTime(runDetail.startedAt)} />
            <DetailMetric
              label="Completed"
              value={runDetail.completedAt ? formatRelativeTime(runDetail.completedAt) : "In progress"}
            />
            <DetailMetric label="Tokens in" value={formatTokenCount(runDetail.tokensIn)} />
            <DetailMetric label="Tokens out" value={formatTokenCount(runDetail.tokensOut)} />
            <DetailMetric label="Cost" value={formatCost(runDetail.costUsd)} />
            <DetailMetric label="Correlation ID" value={runDetail.correlationId || "—"} />
          </div>
        </LayerSection>

        <LayerSection title="Layer 2: Technical Verification">
          {runDetail.review ? (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <ReviewBadge verdict={runDetail.review.verdict} />
                {runDetail.review.reviewerModel && (
                  <span className="text-11 text-tertiary">{runDetail.review.reviewerModel}</span>
                )}
                <span className="text-11 text-placeholder">{formatRelativeTime(runDetail.review.reviewedAt)}</span>
              </div>
              <p className="text-13 leading-5 text-secondary">{runDetail.review.reason}</p>
            </div>
          ) : (
            <p className="text-13 text-tertiary">Awaiting review</p>
          )}
        </LayerSection>

        <LayerSection title="Layer 3: Progression">
          {runDetail.progressionOutcome ? (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={PROGRESSION_VARIANTS[runDetail.progressionOutcome]} size="sm" disabled>
                  {PROGRESSION_OUTCOME_LABELS[runDetail.progressionOutcome]}
                </Badge>
                {runDetail.progressionEvaluatedAt && (
                  <span className="text-11 text-placeholder">
                    {formatRelativeTime(runDetail.progressionEvaluatedAt)}
                  </span>
                )}
              </div>
              {runDetail.progressionReason && (
                <p className="text-13 leading-5 text-secondary">{runDetail.progressionReason}</p>
              )}
            </div>
          ) : (
            <p className="text-13 text-tertiary">Pending</p>
          )}
        </LayerSection>

        <LayerSection title="Layer 4: Business Acceptance">
          {runDetail.progressionOutcome === "auto_progress" ? (
            <p className="text-13 text-tertiary">Not required</p>
          ) : needsDisposition ? (
            <DispositionAction
              workspaceSlug={workspaceSlug}
              projectId={projectId}
              runId={runId}
              status="pending"
              onComplete={() => {
                mutate();
                globalMutate((key) => typeof key === "string" && key.includes("AGENT_INFRA"), undefined, {
                  revalidate: true,
                });
              }}
            />
          ) : runDetail.disposition ? (
            <div className="flex items-center gap-2">
              <Badge
                variant={
                  runDetail.disposition.status === "approved"
                    ? "accent-success"
                    : runDetail.disposition.status === "rejected"
                      ? "accent-destructive"
                      : "accent-warning"
                }
                size="sm"
                disabled
              >
                {DISPOSITION_STATUS_LABELS[runDetail.disposition.status]}
              </Badge>
              {runDetail.disposition.resolvedAt && (
                <span className="text-11 text-placeholder">{formatRelativeTime(runDetail.disposition.resolvedAt)}</span>
              )}
            </div>
          ) : (
            <p className="text-13 text-tertiary">Pending</p>
          )}
        </LayerSection>

        <LayerSection title="Artifacts">
          {runDetail.artifacts.length === 0 ? (
            <p className="text-13 text-tertiary">No artifacts</p>
          ) : (
            <div className="space-y-2">
              {runDetail.artifacts.map((artifact) => {
                const downloadUrl = `/api/v1/workspaces/${workspaceSlug}/projects/${projectId}/agent-runs/${runId}/artifact-references/${artifact.id}/download/`;
                const isExpired = artifact.expiresAt && new Date(artifact.expiresAt) < now;

                return (
                  <div
                    key={artifact.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-subtle bg-layer-2 px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-tertiary" />
                      <span className="truncate text-13 font-medium text-primary">{artifact.artifactType}</span>
                      <Badge variant="outline-neutral" size="sm" disabled>
                        {artifact.classification}
                      </Badge>
                      {artifact.expiresAt && (
                        <span className={`text-11 ${isExpired ? "text-danger-primary" : "text-tertiary"}`}>
                          {isExpired ? "Expired" : `Expires ${formatRelativeTime(artifact.expiresAt)}`}
                        </span>
                      )}
                    </div>
                    {!isExpired && (
                      <a
                        href={downloadUrl}
                        className="inline-flex items-center gap-1 text-11 font-medium text-accent-primary hover:underline"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </LayerSection>

        <LayerSection title="Context Manifests">
          {runDetail.contextManifests.length === 0 ? (
            <p className="text-13 text-tertiary">No context manifests</p>
          ) : (
            <div className="space-y-2">
              {runDetail.contextManifests.map((manifest) => (
                <div
                  key={manifest.id}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-subtle bg-layer-2 px-3 py-2"
                >
                  <span className="text-13 font-medium text-primary">
                    {manifest.sourceName ?? manifest.knowledgeVersionId}
                  </span>
                  <Badge variant="outline-neutral" size="sm" disabled>
                    v{manifest.versionNumber}
                  </Badge>
                  {manifest.boundAt && (
                    <span className="text-11 text-tertiary">Bound {formatRelativeTime(manifest.boundAt)}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </LayerSection>
      </div>
    </div>
  );
}

function RunDetailHeader(props: { agentRef?: string; onClose?: () => void }) {
  const { agentRef, onClose } = props;

  return (
    <div className="flex items-center justify-between border-b border-subtle px-4 py-3">
      <div>
        <h2 className="text-16 font-semibold text-primary">Run detail</h2>
        {agentRef && <p className="text-11 text-tertiary">{agentRef}</p>}
      </div>
      {onClose && (
        <Button variant="link-neutral" size="sm" onClick={onClose} aria-label="Close run detail">
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

function LayerSection(props: { title: string; children: ReactNode }) {
  const { title, children } = props;

  return (
    <section className="rounded-lg border border-subtle bg-surface-1 p-4">
      <h3 className="mb-3 text-12 font-semibold tracking-wide text-tertiary uppercase">{title}</h3>
      {children}
    </section>
  );
}

function DetailMetric(props: { label: string; value: string }) {
  const { label, value } = props;

  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-11 text-placeholder">{label}</span>
      <span className="text-13 font-medium text-secondary">{value}</span>
    </div>
  );
}
