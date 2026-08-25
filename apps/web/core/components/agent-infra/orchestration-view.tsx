/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { Activity, Bot, CheckCircle2, XCircle, Clock, ChevronRight } from "lucide-react";
import { Loader } from "@plane/ui";
import { useAgentInfraAssignments } from "@/hooks/use-agent-infra";
import type { TAgentAssignment, TAgentRun } from "./mock-data";

type TOrchestrationViewProps = {
  workspaceSlug?: string;
  projectId?: string;
};

type AgentNode = {
  id: string;
  name: string;
  assignments: TAgentAssignment[];
  running: number;
  completed: number;
  failed: number;
  pending: number;
  total: number;
};

const AGENT_PALETTE = [
  { bg: "bg-indigo-500/10", text: "text-indigo-400", ring: "ring-indigo-500/40", fill: "#6366f1" },
  { bg: "bg-orange-500/10", text: "text-orange-400", ring: "ring-orange-500/40", fill: "#f97316" },
  { bg: "bg-emerald-500/10", text: "text-emerald-400", ring: "ring-emerald-500/40", fill: "#10b981" },
  { bg: "bg-purple-500/10", text: "text-purple-400", ring: "ring-purple-500/40", fill: "#a855f7" },
  { bg: "bg-cyan-500/10", text: "text-cyan-400", ring: "ring-cyan-500/40", fill: "#06b6d4" },
  { bg: "bg-rose-500/10", text: "text-rose-400", ring: "ring-rose-500/40", fill: "#f43f5e" },
];

function getAgentColor(index: number) {
  return AGENT_PALETTE[index % AGENT_PALETTE.length];
}

function formatAgentLabel(agentRef: string): string {
  const parts = agentRef.replace("agents/", "").split("-");
  return parts.map((p) => p.charAt(0).toUpperCase()).join("");
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-custom-background-80 text-custom-text-300",
    running: "bg-blue-500/10 text-blue-400",
    completed: "bg-green-500/10 text-green-400",
    failed: "bg-red-500/10 text-red-400",
    cancelled: "bg-yellow-500/10 text-yellow-400",
    success: "bg-green-500/10 text-green-400",
    failure: "bg-red-500/10 text-red-400",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide ${styles[status] ?? styles.pending}`}
    >
      {status}
    </span>
  );
}

function AgentNodeCard({
  agent,
  colorIndex,
  isSelected,
  onClick,
}: {
  agent: AgentNode;
  colorIndex: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  const color = getAgentColor(colorIndex);
  const isRunning = agent.running > 0;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`group relative flex flex-col items-center gap-2 rounded-xl border p-4 transition-all ${
        isSelected
          ? "border-accent-primary bg-accent-primary/5"
          : "hover:border-accent-primary/40 border-subtle bg-surface-1 hover:bg-layer-1"
      }`}
      style={{ minWidth: 120 }}
    >
      <div
        className={`relative flex h-14 w-14 items-center justify-center rounded-full ${color.bg} ring-2 ${color.ring}`}
      >
        <span className={`text-lg font-bold ${color.text}`}>{formatAgentLabel(agent.id)}</span>
        {isRunning && (
          <span className="absolute -top-0.5 -right-0.5 flex h-3 w-3">
            <span className="bg-blue-400 absolute inline-flex h-full w-full animate-ping rounded-full opacity-75" />
            <span className="bg-blue-500 relative inline-flex h-3 w-3 rounded-full" />
          </span>
        )}
        {agent.failed > 0 && (
          <span className="bg-red-500 absolute -right-0.5 -bottom-0.5 flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white">
            {agent.failed}
          </span>
        )}
      </div>

      <span className="text-12 font-medium text-primary">{agent.name}</span>

      <div className="flex items-center gap-2 text-11 text-tertiary">
        <span>
          {agent.completed}/{agent.total}
        </span>
      </div>
    </button>
  );
}

function AgentDetailPanel({ agent, colorIndex }: { agent: AgentNode; colorIndex: number }) {
  const color = getAgentColor(colorIndex);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className={`flex h-8 w-8 items-center justify-center rounded-full ${color.bg}`}>
          <span className={`text-sm font-bold ${color.text}`}>{formatAgentLabel(agent.id)}</span>
        </div>
        <div>
          <h3 className="text-14 font-semibold text-primary">{agent.name}</h3>
          <p className="text-11 text-tertiary">{agent.id}</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {[
          { label: "Total", value: agent.total, icon: Bot },
          { label: "Active", value: agent.running, icon: Activity },
          { label: "Done", value: agent.completed, icon: CheckCircle2 },
          { label: "Failed", value: agent.failed, icon: XCircle },
        ].map((stat) => (
          <div key={stat.label} className="flex flex-col items-center rounded-md bg-layer-2 px-2 py-2">
            <stat.icon className="mb-1 h-3 w-3 text-tertiary" />
            <span className="text-16 font-bold text-primary">{stat.value}</span>
            <span className="tracking-wider text-[9px] text-tertiary uppercase">{stat.label}</span>
          </div>
        ))}
      </div>

      <div>
        <h4 className="tracking-wider mb-2 text-12 font-semibold text-tertiary uppercase">
          Work Items ({agent.assignments.length})
        </h4>
        {agent.assignments.length === 0 ? (
          <div className="rounded-md border border-dashed border-subtle px-3 py-6 text-center text-12 text-tertiary">
            No assignments for this agent
          </div>
        ) : (
          <div className="space-y-2">
            {agent.assignments.map((assignment) => (
              <div key={assignment.id} className="rounded-md border border-subtle bg-layer-1 px-3 py-2.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-13 leading-snug font-medium text-primary">
                    {assignment.agentName || assignment.agentRef}
                  </span>
                  <StatusBadge status={assignment.status} />
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-11 text-tertiary">
                  <span>{assignment.assignmentType}</span>
                  <span>·</span>
                  <span>{new Date(assignment.createdAt).toLocaleString()}</span>
                </div>
                {assignment.runs.length > 0 && (
                  <div className="mt-2 space-y-1 border-t border-subtle pt-2">
                    {assignment.runs.slice(0, 3).map((run: TAgentRun) => (
                      <div key={run.id} className="flex items-center justify-between text-11">
                        <span className="text-secondary">{run.model}</span>
                        <div className="flex items-center gap-2">
                          <StatusBadge status={run.outcome} />
                          {run.startedAt && (
                            <span className="text-quaternary">{new Date(run.startedAt).toLocaleTimeString()}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function OrchestrationView({ workspaceSlug, projectId }: TOrchestrationViewProps) {
  const { assignments, isLoading } = useAgentInfraAssignments(workspaceSlug, projectId);

  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const agentNodes: AgentNode[] = useMemo(() => {
    if (!assignments) return [];

    const agentMap = new Map<string, TAgentAssignment[]>();
    for (const assignment of assignments) {
      const ref = assignment.agentRef;
      if (!agentMap.has(ref)) agentMap.set(ref, []);
      agentMap.get(ref)!.push(assignment);
    }

    return Array.from(agentMap.entries()).map(([ref, agentAssignments]) => ({
      id: ref,
      name: ref
        .replace("agents/", "")
        .replace(/-/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase()),
      assignments: agentAssignments,
      running: agentAssignments.filter((a) => a.status === "running").length,
      completed: agentAssignments.filter((a) => a.status === "completed").length,
      failed: agentAssignments.filter((a) => a.status === "failed").length,
      pending: agentAssignments.filter((a) => a.status === "pending").length,
      total: agentAssignments.length,
    }));
  }, [assignments]);

  const selectedAgent = agentNodes.find((a) => a.id === selectedAgentId);
  const selectedIndex = agentNodes.findIndex((a) => a.id === selectedAgentId);

  const totalAssignments = assignments?.length ?? 0;
  const runningCount = assignments?.filter((a) => a.status === "running").length ?? 0;
  const completedCount = assignments?.filter((a) => a.status === "completed").length ?? 0;
  const failedCount = assignments?.filter((a) => a.status === "failed").length ?? 0;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Loader className="space-y-3">
          <Loader.Item height="80px" />
          <Loader.Item height="200px" />
        </Loader>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-18 font-semibold text-primary">Agent Orchestration</h2>
        <p className="mt-1 text-13 text-tertiary">
          Live view of agent activity. Click an agent to inspect its assignments.
        </p>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total", value: totalAssignments, color: "text-accent-primary" },
          { label: "Running", value: runningCount, color: "text-blue-400" },
          { label: "Completed", value: completedCount, color: "text-green-400" },
          { label: "Failed", value: failedCount, color: "text-red-400" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-center">
            <div className={`text-xl font-bold ${stat.color}`}>{stat.value}</div>
            <div className="tracking-wider text-11 text-tertiary uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Agent nodes + detail */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <div className="rounded-lg border border-subtle bg-surface-1 p-4">
            <h3 className="tracking-wider mb-4 text-13 font-semibold text-tertiary uppercase">
              Agents ({agentNodes.length})
            </h3>

            {agentNodes.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
                <Bot className="h-8 w-8 text-tertiary" />
                <p className="text-13 font-medium text-secondary">No agents active</p>
                <p className="text-11 text-tertiary">
                  Agent assignments will appear here when work items are processed.
                </p>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap gap-3">
                  {agentNodes.map((agent, i) => (
                    <AgentNodeCard
                      key={agent.id}
                      agent={agent}
                      colorIndex={i}
                      isSelected={selectedAgentId === agent.id}
                      onClick={() => setSelectedAgentId(selectedAgentId === agent.id ? null : agent.id)}
                    />
                  ))}
                </div>

                {/* Pipeline flow indicator */}
                {agentNodes.length > 1 && (
                  <div className="mt-4 flex items-center justify-center gap-1 text-11 text-tertiary">
                    {agentNodes.map((agent, i) => (
                      <span key={agent.id} className="flex items-center gap-1">
                        <span className="font-medium">{formatAgentLabel(agent.id)}</span>
                        {i < agentNodes.length - 1 && <ChevronRight className="h-3 w-3" />}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Activity feed */}
          <div className="mt-4 rounded-lg border border-subtle bg-surface-1 p-4">
            <div className="mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4 text-tertiary" />
              <h3 className="tracking-wider text-13 font-semibold text-tertiary uppercase">Recent Activity</h3>
            </div>
            {!assignments || assignments.length === 0 ? (
              <p className="py-4 text-center text-12 text-tertiary">No activity yet</p>
            ) : (
              <div className="space-y-1">
                {assignments
                  .slice()
                  .toSorted((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
                  .slice(0, 15)
                  .map((a) => (
                    <div key={a.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-12 hover:bg-layer-1">
                      <StatusBadge status={a.status} />
                      <span className="flex-1 truncate text-secondary">
                        {a.agentName || a.agentRef} — {a.assignmentType}
                      </span>
                      <span className="text-quaternary shrink-0 text-11">
                        {new Date(a.createdAt).toLocaleTimeString()}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>

        {/* Detail sidebar */}
        <div className="xl:col-span-1">
          <div className="sticky top-6 rounded-lg border border-subtle bg-surface-1 p-4">
            {selectedAgent ? (
              <AgentDetailPanel agent={selectedAgent} colorIndex={selectedIndex} />
            ) : (
              <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
                <Bot className="h-6 w-6 text-tertiary" />
                <p className="text-13 text-secondary">Click an agent to inspect</p>
                <p className="text-11 text-tertiary">View work items, runs, and failure details</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
