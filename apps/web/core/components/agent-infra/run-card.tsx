/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ChevronDownIcon } from "@plane/propel/icons";
import { Disclosure, Transition } from "@headlessui/react";
import type { TBadgeVariant } from "@plane/ui";
import { Badge } from "@plane/ui";
import { DispositionAction } from "./disposition-action";
import type { TAgentRun } from "./mock-data";
import {
  RUN_OUTCOME_LABELS,
  formatCost,
  formatDuration,
  formatRelativeTime,
  formatRunningDuration,
  formatTokenCount,
  isReviewStale,
} from "./mock-data";
import { ReviewBadge } from "./review-badge";

type TRunCardProps = {
  run: TAgentRun;
  defaultExpanded?: boolean;
};

const OUTCOME_VARIANTS: Record<TAgentRun["outcome"], TBadgeVariant> = {
  success: "accent-success",
  failure: "accent-destructive",
  partial: "accent-warning",
};

export function RunCard(props: TRunCardProps) {
  const { run, defaultExpanded = false } = props;
  const hasReview = Boolean(run.review);
  const isActive = Boolean(run.isActive);
  const isCompleted = Boolean(run.completedAt) && !isActive;
  const reviewStale = isReviewStale(run);
  const needsDisposition = run.review && (run.review.verdict === "flagged" || run.review.verdict === "escalated");

  const durationLabel = isActive ? formatRunningDuration(run.startedAt) : formatDuration(run.durationMs);

  return (
    <div className="rounded-md border border-subtle bg-layer-2">
      <Disclosure defaultOpen={defaultExpanded}>
        {({ open }) => (
          <>
            <Disclosure.Button
              className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
              disabled={!hasReview}
            >
              <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                <span className="text-11 font-medium text-tertiary">Attempt {run.attempt}</span>
                <Badge variant={OUTCOME_VARIANTS[run.outcome]} size="sm" disabled>
                  {RUN_OUTCOME_LABELS[run.outcome]}
                </Badge>
                <span className="truncate text-13 font-medium text-primary">{run.model}</span>
                {hasReview && (
                  <span className="border-green-500 bg-green-50 text-green-700 rounded-md border border-solid px-2 py-0.5 text-11 font-medium">
                    Confirmed
                  </span>
                )}
                {isCompleted && !hasReview && (
                  <span className="border-amber-500 text-amber-700 rounded-md border border-dashed px-2 py-0.5 text-11 font-medium">
                    Pending verification
                  </span>
                )}
                {reviewStale && (
                  <span className="text-orange-500 text-11 italic">
                    Review overdue ({formatRelativeTime(run.completedAt!)})
                  </span>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <div className="hidden items-center gap-3 sm:flex">
                  <Metric label="Duration" value={durationLabel} />
                  <Metric label="Tokens" value={formatTokenCount(run.tokenCount)} />
                  <Metric label="Cost" value={formatCost(run.costUsd)} />
                </div>
                {hasReview && (
                  <ChevronDownIcon
                    className={`h-3.5 w-3.5 text-tertiary transition-transform ${open ? "rotate-180" : ""}`}
                  />
                )}
              </div>
            </Disclosure.Button>

            <div className="flex flex-wrap gap-3 border-t border-subtle px-3 py-2 sm:hidden">
              <Metric label="Duration" value={durationLabel} />
              <Metric label="Tokens" value={formatTokenCount(run.tokenCount)} />
              <Metric label="Cost" value={formatCost(run.costUsd)} />
            </div>

            {hasReview && (
              <Transition
                show={open}
                enter="transition-all duration-200 ease-out"
                enterFrom="opacity-0"
                enterTo="opacity-100"
                leave="transition-all duration-150 ease-in"
                leaveFrom="opacity-100"
                leaveTo="opacity-0"
              >
                <Disclosure.Panel static>
                  <div className="space-y-3 border-t border-subtle px-3 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-11 text-tertiary">Authorizing review</span>
                      <ReviewBadge verdict={run.review!.verdict} />
                      <span className="text-11 text-placeholder">{formatRelativeTime(run.review!.reviewedAt)}</span>
                    </div>
                    <p className="text-13 leading-5 text-secondary">{run.review!.reason}</p>
                    {needsDisposition && run.disposition && (
                      <DispositionAction status={run.disposition.status} compact />
                    )}
                  </div>
                </Disclosure.Panel>
              </Transition>
            )}
          </>
        )}
      </Disclosure>
    </div>
  );
}

function Metric(props: { label: string; value: string }) {
  const { label, value } = props;

  return (
    <div className="flex flex-col">
      <span className="text-11 text-placeholder">{label}</span>
      <span className="text-11 font-medium text-secondary">{value}</span>
    </div>
  );
}
