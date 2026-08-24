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

// --- P7: Authorization Policy types ---

export type TPolicyScope = "workspace" | "project";
export type TPolicyEffect = "allow" | "deny" | "require_approval";
export type TPolicyStatus = "draft" | "pending_approval" | "active" | "deprecated" | "revoked";
export type TPolicyAutonomyClassification = "unattended" | "supervised" | "attended";

export type TPolicySubject = {
  type: string;
  ref: string;
  conditions?: Record<string, unknown> | null;
};

export type TPolicyResource = {
  type: string;
  ref: string;
  conditions?: Record<string, unknown> | null;
};

export type TPolicyAction = {
  name: string;
  constraints?: Record<string, unknown> | null;
};

export type TPolicySoDRule = {
  name: string;
  description: string;
  conflicting_actions: string[];
  scope: string;
};

export type TAuthorizationPolicy = {
  id: string;
  workspace: string;
  project?: string | null;
  name: string;
  version: string;
  description: string;
  scope: TPolicyScope;
  priority: number;
  effect: TPolicyEffect;
  subjects: TPolicySubject[];
  resources: TPolicyResource[];
  actions: TPolicyAction[];
  conditions?: Record<string, unknown> | null;
  separation_of_duty?: TPolicySoDRule[] | null;
  autonomy_classification: TPolicyAutonomyClassification;
  emergency: boolean;
  status: TPolicyStatus;
  content_hash: string;
  revision_number: number;
  previous_revision?: string | null;
  expires_at?: string | null;
  owner: string;
  approved_by?: string | null;
  approved_at?: string | null;
  revoked_by?: string | null;
  revoked_at?: string | null;
  revocation_reason?: string | null;
  created_at: string;
  updated_at: string;
};

export type TAuthorizationPolicyListItem = {
  id: string;
  name: string;
  version: string;
  description: string;
  scope: TPolicyScope;
  priority: number;
  effect: TPolicyEffect;
  autonomy_classification: TPolicyAutonomyClassification;
  emergency: boolean;
  status: TPolicyStatus;
  revision_number: number;
  owner: string;
  created_at: string;
  updated_at: string;
};

export type TDecisionOutcome = "allow" | "deny" | "require_approval";

export type TPolicyDecision = {
  id: string;
  workspace: string;
  project?: string | null;
  subject_type: string;
  subject_ref: string;
  resource_type: string;
  resource_ref: string;
  action: string;
  outcome: TDecisionOutcome;
  matching_policies: string[];
  deciding_policy?: string | null;
  evaluation_context: Record<string, unknown>;
  reason: string;
  evaluated_at: string;
  correlation_id?: string;
  run?: string | null;
  created_at: string;
};

export type TApprovalStatus = "pending" | "approved" | "rejected" | "expired" | "cancelled";

export type TActionApproval = {
  id: string;
  workspace: string;
  project?: string | null;
  policy_decision: string;
  subject_type: string;
  subject_ref: string;
  action: string;
  target_type: string;
  target_ref: string;
  target_digest: string;
  target_diff?: Record<string, unknown> | null;
  credential_scope?: Record<string, unknown> | null;
  budget_impact?: Record<string, unknown> | null;
  risk_level: string;
  status: TApprovalStatus;
  requested_by?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_reason?: string | null;
  expires_at?: string | null;
  is_expired: boolean;
  correlation_id?: string;
  created_at: string;
  updated_at: string;
};

export type TEmergencyDeny = {
  id: string;
  workspace: string;
  project?: string | null;
  policy?: string | null;
  reason: string;
  activated_by?: string | null;
  activated_at: string;
  scope_filter?: Record<string, unknown> | null;
  is_active: boolean;
  deactivated_by?: string | null;
  deactivated_at?: string | null;
  deactivation_reason?: string | null;
  incident_reference?: string | null;
  created_at: string;
  updated_at: string;
};

export type TConstraintScope = "run" | "assignment" | "project" | "workspace";

export type TSeparationOfDutyConstraint = {
  id: string;
  workspace: string;
  project?: string | null;
  policy: string;
  name: string;
  description: string;
  conflicting_actions: string[];
  scope: TConstraintScope;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TPolicySimulationResult = {
  outcome: TDecisionOutcome;
  deciding_policy?: string | null;
  reason: string;
  matching_policies: Array<{ id: string; name: string; effect: TPolicyEffect; priority: number }>;
  sod_violations: Array<{ constraint: string; description: string }>;
  emergency_deny_active: boolean;
};

export type TPolicyDiffResult = {
  policy_a: { id: string; name: string; version: string };
  policy_b: { id: string; name: string; version: string };
  changes: Array<{
    field: string;
    old_value: unknown;
    new_value: unknown;
  }>;
  impact_summary: string;
};

export type TPolicyBlastRadiusResult = {
  policy: { id: string; name: string };
  affected_agents: string[];
  affected_resources: string[];
  affected_actions: string[];
  total_decisions_affected: number;
  risk_assessment: string;
};
