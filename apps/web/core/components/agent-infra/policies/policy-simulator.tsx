/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Play, ShieldX, XCircle } from "lucide-react";
import agentInfraService from "@/services/agent-infra.service";
import type { TPolicySimulationResult } from "../governance-types";

type TPolicySimulatorProps = {
  workspaceSlug: string;
  projectId: string;
};

const OUTCOME_CONFIG = {
  allow: { icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50 dark:bg-emerald-950/30", label: "ALLOW" },
  deny: { icon: XCircle, color: "text-red-600", bg: "bg-red-50 dark:bg-red-950/30", label: "DENY" },
  require_approval: {
    icon: AlertTriangle,
    color: "text-amber-600",
    bg: "bg-amber-50 dark:bg-amber-950/30",
    label: "REQUIRE APPROVAL",
  },
};

export function PolicySimulator(props: TPolicySimulatorProps) {
  const { workspaceSlug, projectId } = props;
  const [subjectType, setSubjectType] = useState("agent");
  const [subjectRef, setSubjectRef] = useState("");
  const [resourceType, setResourceType] = useState("work_item");
  const [resourceRef, setResourceRef] = useState("");
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TPolicySimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSimulate = async () => {
    if (!subjectRef || !action) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await agentInfraService.simulatePolicy(workspaceSlug, projectId, {
        subject_type: subjectType,
        subject_ref: subjectRef,
        resource_type: resourceType,
        resource_ref: resourceRef || "*",
        action,
      });
      setResult(res as TPolicySimulationResult);
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err ? String(err.message) : "Simulation failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const outcomeConfig = result ? OUTCOME_CONFIG[result.outcome] : null;
  const OutcomeIcon = outcomeConfig?.icon ?? ShieldX;

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-5">
      <h3 className="text-14 font-semibold text-primary">Grant Simulation</h3>
      <p className="mt-1 text-12 text-tertiary">
        Test what outcome the policy evaluator would produce for a given request. No side effects.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="sim-subject-type" className="text-12 font-medium text-secondary">
            Subject Type
          </label>
          <select
            id="sim-subject-type"
            value={subjectType}
            onChange={(e) => setSubjectType(e.target.value)}
            className="mt-1 w-full rounded-md border border-subtle bg-surface-1 px-3 py-1.5 text-13"
          >
            <option value="agent">Agent</option>
            <option value="service">Service</option>
            <option value="user">User</option>
          </select>
        </div>
        <div>
          <label htmlFor="sim-subject-ref" className="text-12 font-medium text-secondary">
            Subject Ref
          </label>
          <input
            id="sim-subject-ref"
            type="text"
            value={subjectRef}
            onChange={(e) => setSubjectRef(e.target.value)}
            placeholder="e.g. dev-engineer"
            className="mt-1 w-full rounded-md border border-subtle bg-surface-1 px-3 py-1.5 text-13"
          />
        </div>
        <div>
          <label htmlFor="sim-resource-type" className="text-12 font-medium text-secondary">
            Resource Type
          </label>
          <select
            id="sim-resource-type"
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            className="mt-1 w-full rounded-md border border-subtle bg-surface-1 px-3 py-1.5 text-13"
          >
            <option value="work_item">Work Item</option>
            <option value="agent_run">Agent Run</option>
            <option value="code_change">Code Change</option>
            <option value="deployment">Deployment</option>
          </select>
        </div>
        <div>
          <label htmlFor="sim-resource-ref" className="text-12 font-medium text-secondary">
            Resource Ref
          </label>
          <input
            id="sim-resource-ref"
            type="text"
            value={resourceRef}
            onChange={(e) => setResourceRef(e.target.value)}
            placeholder="e.g. * (wildcard)"
            className="mt-1 w-full rounded-md border border-subtle bg-surface-1 px-3 py-1.5 text-13"
          />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="sim-action" className="text-12 font-medium text-secondary">
            Action
          </label>
          <input
            id="sim-action"
            type="text"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="e.g. execute, verify, approve_disposition"
            className="mt-1 w-full rounded-md border border-subtle bg-surface-1 px-3 py-1.5 text-13"
          />
        </div>
      </div>

      <button
        type="button"
        disabled={loading || !subjectRef || !action}
        onClick={handleSimulate}
        className="mt-4 flex items-center gap-2 rounded-md bg-accent-primary px-4 py-2 text-13 font-medium text-white hover:bg-accent-primary/90 disabled:opacity-50"
      >
        <Play className="h-3.5 w-3.5" />
        {loading ? "Simulating…" : "Simulate"}
      </button>

      {error && (
        <div className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300 mt-4 rounded-md border px-4 py-3 text-13">
          {error}
        </div>
      )}

      {result && outcomeConfig && (
        <div className={`mt-4 rounded-lg border border-subtle ${outcomeConfig.bg} p-4`}>
          <div className="flex items-center gap-2">
            <OutcomeIcon className={`h-5 w-5 ${outcomeConfig.color}`} />
            <span className={`text-16 font-bold ${outcomeConfig.color}`}>{outcomeConfig.label}</span>
          </div>
          <p className="mt-2 text-13 text-secondary">{result.reason}</p>

          {result.emergency_deny_active && (
            <div className="bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300 mt-3 flex items-center gap-2 rounded-md px-3 py-2 text-12">
              <ShieldX className="h-4 w-4" />
              Emergency deny is active
            </div>
          )}

          {result.matching_policies.length > 0 && (
            <div className="mt-3">
              <p className="text-12 font-medium text-secondary">Matching policies:</p>
              <div className="mt-1 space-y-1">
                {result.matching_policies.map((mp) => (
                  <div key={mp.id} className="flex items-center gap-2 text-12 text-secondary">
                    <span className="font-mono">[{mp.priority}]</span>
                    <span>{mp.name}</span>
                    <span className="text-tertiary">({mp.effect})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.sod_violations.length > 0 && (
            <div className="mt-3">
              <p className="text-red-600 text-12 font-medium">SoD violations:</p>
              <div className="mt-1 space-y-1">
                {result.sod_violations.map((v) => (
                  <p key={v.constraint} className="text-red-500 text-12">
                    {v.constraint}: {v.description}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
