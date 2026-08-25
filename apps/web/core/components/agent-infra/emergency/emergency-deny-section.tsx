/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { AlertOctagon, Power, PowerOff, ShieldX } from "lucide-react";
import { Loader } from "@plane/ui";
import { useEmergencyDenies } from "@/hooks/use-agent-infra";
import agentInfraService from "@/services/agent-infra.service";
import type { TEmergencyDeny } from "../governance-types";

type TEmergencyDenySectionProps = {
  workspaceSlug: string;
  projectId: string;
};

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
}

export function EmergencyDenySection(props: TEmergencyDenySectionProps) {
  const { workspaceSlug, projectId } = props;
  const { emergencyDenies, isLoading, error, mutate } = useEmergencyDenies(workspaceSlug, projectId);
  const [showActivateForm, setShowActivateForm] = useState(false);
  const [activateReason, setActivateReason] = useState("");
  const [incidentRef, setIncidentRef] = useState("");
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null);
  const [deactivateReason, setDeactivateReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const activeDenies = (emergencyDenies ?? []).filter((d) => (d as TEmergencyDeny).is_active);
  const inactiveDenies = (emergencyDenies ?? []).filter((d) => !(d as TEmergencyDeny).is_active);

  const handleActivate = async () => {
    if (!activateReason.trim()) return;
    setActionLoading(true);
    try {
      await agentInfraService.activateEmergencyDeny(workspaceSlug, projectId, {
        reason: activateReason,
        incident_reference: incidentRef || undefined,
      });
      await mutate();
      setShowActivateForm(false);
      setActivateReason("");
      setIncidentRef("");
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeactivate = async (emergencyId: string) => {
    if (!deactivateReason.trim()) return;
    setActionLoading(true);
    try {
      await agentInfraService.deactivateEmergencyDeny(workspaceSlug, projectId, emergencyId, deactivateReason);
      await mutate();
      setDeactivatingId(null);
      setDeactivateReason("");
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="100px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldX className="text-red-500 h-4 w-4" />
          <div>
            <h3 className="text-14 font-semibold text-primary">Emergency Deny</h3>
            <p className="text-11 text-tertiary">Kill-switch to block all agent actions immediately.</p>
          </div>
        </div>
        {!showActivateForm && (
          <button
            type="button"
            onClick={() => setShowActivateForm(true)}
            className="bg-red-600 hover:bg-red-700 flex items-center gap-1.5 rounded-md px-3 py-1.5 text-12 font-medium text-white"
          >
            <AlertOctagon className="h-3.5 w-3.5" />
            Activate Emergency Deny
          </button>
        )}
      </div>

      {showActivateForm && (
        <div className="border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-950/30 rounded-lg border-2 p-4">
          <div className="text-red-700 dark:text-red-300 flex items-center gap-2">
            <AlertOctagon className="h-5 w-5" />
            <h4 className="text-14 font-semibold">Activate Emergency Deny</h4>
          </div>
          <p className="text-red-600 dark:text-red-400 mt-1 text-12">
            This will immediately block all agent actions in this project. Use only in emergencies.
          </p>
          <div className="mt-3 space-y-2">
            <div>
              <label htmlFor="ed-reason" className="text-red-700 dark:text-red-300 text-12 font-medium">
                Reason *
              </label>
              <input
                id="ed-reason"
                type="text"
                value={activateReason}
                onChange={(e) => setActivateReason(e.target.value)}
                placeholder="Why are you activating emergency deny?"
                className="border-red-300 dark:border-red-700 dark:bg-red-950/50 mt-1 w-full rounded-md border bg-white px-3 py-1.5 text-13"
              />
            </div>
            <div>
              <label htmlFor="ed-incident" className="text-red-700 dark:text-red-300 text-12 font-medium">
                Incident Reference
              </label>
              <input
                id="ed-incident"
                type="text"
                value={incidentRef}
                onChange={(e) => setIncidentRef(e.target.value)}
                placeholder="e.g. INC-1234 (optional)"
                className="border-red-300 dark:border-red-700 dark:bg-red-950/50 mt-1 w-full rounded-md border bg-white px-3 py-1.5 text-13"
              />
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={actionLoading || !activateReason.trim()}
              onClick={handleActivate}
              className="bg-red-600 hover:bg-red-700 rounded-md px-4 py-1.5 text-12 font-medium text-white disabled:opacity-50"
            >
              {actionLoading ? "Activating…" : "Confirm Activate"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowActivateForm(false);
                setActivateReason("");
                setIncidentRef("");
              }}
              className="rounded-md border border-subtle px-4 py-1.5 text-12 font-medium text-secondary hover:bg-layer-1"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/30 rounded-md border px-4 py-3 text-13">
          Failed to load emergency denies.
        </div>
      )}

      {activeDenies.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-red-600 text-13 font-semibold">Active Emergency Denies</h4>
          {activeDenies.map((deny) => {
            const d = deny as TEmergencyDeny;
            const isDeactivating = deactivatingId === d.id;
            return (
              <div
                key={d.id}
                className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/20 rounded-lg border-2 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Power className="text-red-600 h-4 w-4" />
                      <span className="text-red-700 dark:text-red-300 text-13 font-semibold">ACTIVE</span>
                      {d.incident_reference && (
                        <span className="bg-red-100 text-red-600 dark:bg-red-900/50 font-mono rounded-sm px-1.5 py-0.5 text-11">
                          {d.incident_reference}
                        </span>
                      )}
                    </div>
                    <p className="text-red-600 dark:text-red-400 text-13">{d.reason}</p>
                    <p className="text-red-500 text-11">Activated: {formatDate(d.activated_at)}</p>
                  </div>
                  <div>
                    {isDeactivating ? (
                      <div className="space-y-2">
                        <label htmlFor={`deactivate-reason-${d.id}`} className="text-12 font-medium text-secondary">
                          Deactivation reason
                        </label>
                        <input
                          id={`deactivate-reason-${d.id}`}
                          type="text"
                          value={deactivateReason}
                          onChange={(e) => setDeactivateReason(e.target.value)}
                          placeholder="Deactivation reason"
                          className="w-full rounded-md border border-subtle bg-white px-3 py-1.5 text-12 dark:bg-surface-1"
                        />
                        <div className="flex gap-1">
                          <button
                            type="button"
                            disabled={actionLoading || !deactivateReason.trim()}
                            onClick={() => handleDeactivate(d.id)}
                            className="bg-emerald-600 hover:bg-emerald-700 flex-1 rounded-md px-2 py-1 text-11 font-medium text-white disabled:opacity-50"
                          >
                            Deactivate
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setDeactivatingId(null);
                              setDeactivateReason("");
                            }}
                            className="rounded-md border border-subtle px-2 py-1 text-11 text-secondary hover:bg-layer-1"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setDeactivatingId(d.id)}
                        className="border-emerald-300 text-emerald-600 hover:bg-emerald-50 dark:border-emerald-700 dark:hover:bg-emerald-950/30 flex items-center gap-1 rounded-md border px-3 py-1.5 text-12 font-medium"
                      >
                        <PowerOff className="h-3.5 w-3.5" />
                        Deactivate
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {inactiveDenies.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-13 font-semibold text-tertiary">History</h4>
          {inactiveDenies.slice(0, 5).map((deny) => {
            const d = deny as TEmergencyDeny;
            return (
              <div key={d.id} className="rounded-lg border border-subtle bg-surface-1 p-3">
                <div className="flex items-center gap-2 text-12 text-secondary">
                  <PowerOff className="h-3.5 w-3.5 text-tertiary" />
                  <span>{d.reason}</span>
                  {d.incident_reference && <span className="font-mono text-tertiary">{d.incident_reference}</span>}
                </div>
                <div className="mt-1 flex gap-3 text-11 text-tertiary">
                  <span>Active: {formatDate(d.activated_at)}</span>
                  <span>Deactivated: {formatDate(d.deactivated_at)}</span>
                </div>
                {d.deactivation_reason && <p className="mt-1 text-11 text-tertiary">Reason: {d.deactivation_reason}</p>}
              </div>
            );
          })}
        </div>
      )}

      {!error && activeDenies.length === 0 && inactiveDenies.length === 0 && !showActivateForm && (
        <div className="rounded-lg border border-dashed border-subtle bg-surface-1 px-6 py-12 text-center">
          <ShieldX className="mx-auto mb-3 h-10 w-10 text-tertiary" />
          <p className="text-14 font-semibold text-primary">No emergency denies</p>
          <p className="mt-1 text-13 text-tertiary">
            Emergency deny is a kill-switch that blocks all agent actions immediately.
          </p>
        </div>
      )}
    </div>
  );
}
