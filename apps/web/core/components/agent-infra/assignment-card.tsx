/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Bot, ChevronDownIcon } from "lucide-react";
import { Disclosure, Transition } from "@headlessui/react";
import type { TBadgeVariant } from "@plane/ui";
import { Badge, Loader } from "@plane/ui";
import type { TAgentAssignment, TAssignmentStatus, TAssignmentType } from "./mock-data";
import { ASSIGNMENT_STATUS_LABELS, ASSIGNMENT_TYPE_LABELS, formatRelativeTime } from "./mock-data";
import { RunTimeline } from "./run-timeline";

type TAssignmentCardProps = {
  assignment: TAgentAssignment;
  isLoading?: boolean;
  defaultExpanded?: boolean;
};

const TYPE_VARIANTS: Record<TAssignmentType, TBadgeVariant> = {
  qa: "outline-success",
  dev: "outline-primary",
  review: "outline-warning",
  research: "outline-neutral",
};

const STATUS_VARIANTS: Record<TAssignmentStatus, TBadgeVariant> = {
  pending: "accent-neutral",
  running: "accent-warning",
  completed: "accent-success",
  failed: "accent-destructive",
  cancelled: "outline-neutral",
};

export function AssignmentCard(props: TAssignmentCardProps) {
  const { assignment, isLoading = false, defaultExpanded = false } = props;

  if (isLoading) {
    return (
      <div className="rounded-lg border border-subtle bg-surface-1 p-4">
        <Loader className="space-y-3">
          <Loader.Item height="16px" width="50%" />
          <Loader.Item height="12px" width="35%" />
          <Loader.Item height="64px" />
        </Loader>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-subtle bg-surface-1">
      <Disclosure defaultOpen={defaultExpanded}>
        {({ open }) => (
          <>
            <Disclosure.Button className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left">
              <div className="flex min-w-0 flex-1 items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent-subtle">
                  <Bot className="h-4 w-4 text-accent-primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-13 font-semibold text-primary">{assignment.agentName}</span>
                    <Badge variant={TYPE_VARIANTS[assignment.assignmentType]} size="sm" disabled>
                      {ASSIGNMENT_TYPE_LABELS[assignment.assignmentType]}
                    </Badge>
                    <Badge variant={STATUS_VARIANTS[assignment.status]} size="sm" disabled>
                      {ASSIGNMENT_STATUS_LABELS[assignment.status]}
                    </Badge>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-11 text-tertiary">
                    <span>{assignment.agentRef}</span>
                    <span>·</span>
                    <span>Assigned {formatRelativeTime(assignment.createdAt)}</span>
                    <span>·</span>
                    <span>
                      {assignment.runs.length} {assignment.runs.length === 1 ? "run" : "runs"}
                    </span>
                  </div>
                </div>
              </div>
              <ChevronDownIcon
                className={`mt-1 h-4 w-4 shrink-0 text-tertiary transition-transform ${open ? "rotate-180" : ""}`}
              />
            </Disclosure.Button>

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
                <div className="border-t border-subtle px-4 py-3">
                  <RunTimeline runs={assignment.runs} />
                </div>
              </Disclosure.Panel>
            </Transition>
          </>
        )}
      </Disclosure>
    </div>
  );
}
