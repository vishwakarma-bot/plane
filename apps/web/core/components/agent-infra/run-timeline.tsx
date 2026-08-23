/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Bot } from "lucide-react";
import { Loader } from "@plane/ui";
import type { TAgentRun } from "./mock-data";
import { RunCard } from "./run-card";

type TRunTimelineProps = {
  runs: TAgentRun[];
  isLoading?: boolean;
};

export function RunTimeline(props: TRunTimelineProps) {
  const { runs, isLoading = false } = props;

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Loader className="space-y-2">
          <Loader.Item height="48px" />
          <Loader.Item height="48px" />
        </Loader>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed border-subtle bg-surface-1 px-3 py-4">
        <Bot className="h-4 w-4 text-tertiary" />
        <div className="flex flex-col">
          <span className="text-13 font-medium text-secondary">No runs yet</span>
          <span className="text-11 text-tertiary">Agent runs will appear here once execution starts.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-11 font-medium uppercase tracking-wide text-tertiary">Run timeline</span>
        <span className="text-11 text-placeholder">
          {runs.length} {runs.length === 1 ? "run" : "runs"}
        </span>
      </div>
      <div className="space-y-2">
        {runs.map((run, index) => (
          <RunCard key={run.id} run={run} defaultExpanded={index === runs.length - 1 && Boolean(run.review)} />
        ))}
      </div>
    </div>
  );
}
