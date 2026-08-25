/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Clock, ShieldAlert, XCircle } from "lucide-react";
import { Loader } from "@plane/ui";
import { useAuthorizationPolicy } from "@/hooks/use-agent-infra";
import agentInfraService from "@/services/agent-infra.service";
import type { TAuthorizationPolicy } from "../governance-types";
import { EFFECT_LABELS, POLICY_EFFECT_BADGE, POLICY_STATUS_BADGE, STATUS_LABELS } from "./policy-types";

type TPolicyDetailProps = {
  workspaceSlug: string;
  projectId: string;
  policyId: string;
  onMutate?: () => void;
};

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}

function renderTags(items: string[]) {
  if (items.length === 0) return <span className="text-13 text-tertiary">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className="rounded-sm bg-layer-2 px-2 py-0.5 text-12 text-secondary">
          {item}
        </span>
      ))}
    </div>
  );
}

export function PolicyDetail(props: TPolicyDetailProps) {
  const { workspaceSlug, projectId, policyId, onMutate } = props;
  const { policy, isLoading, mutate } = useAuthorizationPolicy(workspaceSlug, projectId, policyId);
  const [actionLoading, setActionLoading] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const [showRevokeForm, setShowRevokeForm] = useState(false);

  const handleApprove = async () => {
    setActionLoading(true);
    try {
      await agentInfraService.approvePolicy(workspaceSlug, projectId, policyId);
      await mutate();
      onMutate?.();
    } catch {
      // error handled by SWR
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokeReason.trim()) return;
    setActionLoading(true);
    try {
      await agentInfraService.revokePolicy(workspaceSlug, projectId, policyId, revokeReason);
      await mutate();
      onMutate?.();
      setShowRevokeForm(false);
      setRevokeReason("");
    } catch {
      // error handled by SWR
    } finally {
      setActionLoading(false);
    }
  };

  if (isLoading || !policy) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="200px" />
      </Loader>
    );
  }

  const p: TAuthorizationPolicy = policy as TAuthorizationPolicy;

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            {p.emergency && <ShieldAlert className="text-red-500 h-5 w-5" />}
            <h3 className="text-16 font-semibold text-primary">{p.name}</h3>
            <span className="text-12 text-tertiary">v{p.version}</span>
          </div>
          <p className="mt-1 text-13 text-secondary">{p.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`inline-flex rounded-sm px-2 py-0.5 text-11 font-medium ${POLICY_EFFECT_BADGE[p.effect]}`}>
            {EFFECT_LABELS[p.effect]}
          </span>
          <span className={`inline-flex rounded-sm px-2 py-0.5 text-11 font-medium ${POLICY_STATUS_BADGE[p.status]}`}>
            {STATUS_LABELS[p.status]}
          </span>
        </div>
      </div>

      {/* Actions */}
      {p.status === "pending_approval" && (
        <div className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 mt-4 flex items-center gap-2 rounded-lg border px-4 py-3">
          <Clock className="text-amber-600 h-4 w-4 shrink-0" />
          <span className="text-amber-900 dark:text-amber-100 flex-1 text-13">This policy is awaiting approval.</span>
          <button
            type="button"
            disabled={actionLoading}
            onClick={handleApprove}
            className="bg-emerald-600 hover:bg-emerald-700 rounded-md px-3 py-1.5 text-12 font-medium text-white disabled:opacity-50"
          >
            {actionLoading ? "Approving…" : "Approve"}
          </button>
        </div>
      )}

      {(p.status === "active" || p.status === "deprecated") && !showRevokeForm && (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => setShowRevokeForm(true)}
            className="border-red-200 text-red-600 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-950/30 rounded-md border px-3 py-1.5 text-12 font-medium"
          >
            Revoke Policy
          </button>
        </div>
      )}

      {showRevokeForm && (
        <div className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30 mt-4 flex items-end gap-2 rounded-lg border px-4 py-3">
          <div className="flex-1">
            <label htmlFor="revoke-reason" className="text-red-700 dark:text-red-300 text-12 font-medium">
              Revocation reason
            </label>
            <input
              id="revoke-reason"
              type="text"
              value={revokeReason}
              onChange={(e) => setRevokeReason(e.target.value)}
              placeholder="Why is this policy being revoked?"
              className="border-red-300 dark:border-red-700 dark:bg-red-950/50 mt-1 w-full rounded-md border bg-white px-3 py-1.5 text-13"
            />
          </div>
          <button
            type="button"
            disabled={actionLoading || !revokeReason.trim()}
            onClick={handleRevoke}
            className="bg-red-600 hover:bg-red-700 rounded-md px-3 py-1.5 text-12 font-medium text-white disabled:opacity-50"
          >
            {actionLoading ? "Revoking…" : "Confirm Revoke"}
          </button>
          <button
            type="button"
            onClick={() => {
              setShowRevokeForm(false);
              setRevokeReason("");
            }}
            className="rounded-md border border-subtle px-3 py-1.5 text-12 font-medium text-secondary hover:bg-layer-1"
          >
            Cancel
          </button>
        </div>
      )}

      {p.revocation_reason && (
        <div className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30 mt-4 flex items-start gap-2 rounded-lg border px-4 py-3">
          <XCircle className="text-red-600 mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="text-red-700 dark:text-red-300 text-13 font-medium">Revoked</p>
            <p className="text-red-600 dark:text-red-400 text-12">{p.revocation_reason}</p>
            <p className="text-red-500 mt-1 text-11">{formatDate(p.revoked_at)}</p>
          </div>
        </div>
      )}

      {/* Metadata grid */}
      <dl className="mt-6 grid gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Scope</dt>
          <dd className="mt-1 text-13 text-primary capitalize">{p.scope}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Priority</dt>
          <dd className="font-mono mt-1 text-13 text-primary">{p.priority}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Autonomy</dt>
          <dd className="mt-1 text-13 text-primary capitalize">{p.autonomy_classification}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Owner</dt>
          <dd className="mt-1 text-13 text-primary">{p.owner}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Revision</dt>
          <dd className="font-mono mt-1 text-13 text-primary">#{p.revision_number}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Content Hash</dt>
          <dd className="font-mono mt-1 text-12 text-secondary">{p.content_hash?.slice(0, 12)}…</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Created</dt>
          <dd className="mt-1 text-13 text-secondary">{formatDate(p.created_at)}</dd>
        </div>
        <div>
          <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Expires</dt>
          <dd className="mt-1 text-13 text-secondary">{formatDate(p.expires_at)}</dd>
        </div>
        {p.approved_at && (
          <div>
            <dt className="text-11 font-medium tracking-wide text-tertiary uppercase">Approved</dt>
            <dd className="mt-1 text-13 text-secondary">{formatDate(p.approved_at)}</dd>
          </div>
        )}
      </dl>

      {/* Subjects, Resources, Actions */}
      <div className="mt-6 space-y-4">
        <div>
          <h4 className="text-13 font-semibold text-primary">Subjects</h4>
          <div className="mt-2 space-y-1">
            {p.subjects.map((s) => (
              <div key={`${s.type}-${s.ref}`} className="flex items-center gap-2 text-13 text-secondary">
                <span className="rounded-sm bg-layer-2 px-2 py-0.5 text-12">{s.type}</span>
                <span className="font-mono text-12">{s.ref}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 className="text-13 font-semibold text-primary">Resources</h4>
          <div className="mt-2 space-y-1">
            {p.resources.map((r) => (
              <div key={`${r.type}-${r.ref}`} className="flex items-center gap-2 text-13 text-secondary">
                <span className="rounded-sm bg-layer-2 px-2 py-0.5 text-12">{r.type}</span>
                <span className="font-mono text-12">{r.ref}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 className="text-13 font-semibold text-primary">Actions</h4>
          <div className="mt-2">{renderTags(p.actions.map((a) => a.name))}</div>
        </div>
        {p.separation_of_duty && p.separation_of_duty.length > 0 && (
          <div>
            <h4 className="text-13 font-semibold text-primary">Separation of Duty Rules</h4>
            <div className="mt-2 space-y-2">
              {p.separation_of_duty.map((sod) => (
                <div key={sod.name} className="rounded-md border border-subtle bg-layer-1 p-3">
                  <p className="text-13 font-medium text-primary">{sod.name}</p>
                  <p className="text-12 text-secondary">{sod.description}</p>
                  <div className="mt-1 flex items-center gap-1">
                    <span className="text-11 text-tertiary">Conflicts:</span>
                    {renderTags(sod.conflicting_actions)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
