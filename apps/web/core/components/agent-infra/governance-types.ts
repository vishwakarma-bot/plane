/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TAutonomyLevel = "supervised" | "semi_autonomous" | "autonomous";

export type TProjectAgentEnablement = {
  id: string;
  agent_ref: string;
  enabled: boolean;
  max_autonomy_level: TAutonomyLevel;
  allowed_assignment_types: string[];
  delegation_permissions: string[];
  enabled_by?: string | null;
  enabled_at?: string | null;
};

export type TModelRoutingConfig = {
  id: string;
  model_ref: string;
  routing_priority: number;
  shadow_mode: boolean;
  budget_limit_usd?: string | null;
  budget_period: "daily" | "weekly" | "monthly";
  budget_used_usd: string;
  eligible_risk_classes: string[];
  eligible_assignment_types: string[];
  enabled: boolean;
};

export type TEnvironmentRevisionStatus = "draft" | "active" | "superseded" | "retired";
export type TDriftStatus = "in_sync" | "drifted" | "unknown";

export type TEnvironmentRevision = {
  id: string;
  environment_ref: string;
  revision_number: number;
  content_hash: string;
  snapshot: Record<string, unknown>;
  status: TEnvironmentRevisionStatus;
  drift_status: TDriftStatus;
  drift_detail?: {
    expected_hash?: string;
    actual_hash?: string;
    fields_changed?: string[];
  } | null;
  last_drift_check_at?: string | null;
};

export type TIntegrationType = "mcp" | "a2a" | "git_ci" | "deployment";
export type TRegistrationStatus = "active" | "suspended" | "degraded" | "retired";
export type THealthStatus = "healthy" | "degraded" | "unreachable" | "unknown";
export type TApprovalClass = "auto" | "manual" | "restricted";

export type TIntegrationRegistration = {
  id: string;
  integration_ref: string;
  integration_type: TIntegrationType;
  server_identity?: string;
  status: TRegistrationStatus;
  health_status: THealthStatus;
  last_health_check_at?: string | null;
  granted_agents: string[];
  granted_scopes: string[];
  approval_class: TApprovalClass;
  failure_rate_percent: string;
};

export type TCatalogEntityType = "agent" | "skill" | "model" | "environment" | "integration";
export type TCatalogRevisionStatus = "draft" | "pending_approval" | "approved" | "rejected" | "rolled_back";

export type TCatalogDiffSummary = {
  added?: string[];
  removed?: string[];
  changed?: Record<string, { old: unknown; new: unknown }>;
};

export type TCatalogRevision = {
  id: string;
  entity_type: TCatalogEntityType;
  entity_ref: string;
  revision_number: number;
  content_hash: string;
  content_snapshot: Record<string, unknown>;
  status: TCatalogRevisionStatus;
  diff_summary?: TCatalogDiffSummary | null;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at?: string;
};

export type TCompatibilityRecord = {
  id: string;
  source_type: string;
  source_ref: string;
  target_type: string;
  target_ref: string;
  compatible: boolean;
  reason?: string;
  last_checked_at?: string;
};

export type TCatalogResponse = {
  status?: string;
  message?: string;
  last_refreshed?: string | null;
  agents?: unknown[];
  skills?: unknown[];
  models?: unknown[];
  environments?: unknown[];
  integrations?: unknown[];
};
