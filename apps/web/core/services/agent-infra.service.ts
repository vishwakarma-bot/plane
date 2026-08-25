/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TAgentInfraPaginatedResponse<T> = {
  results: T[];
  next_cursor?: string | null;
  prev_cursor?: string | null;
  total_count?: number;
};

export type TAgentInfraListParams = {
  cursor?: string;
  per_page?: number;
  status?: string;
  drift_type?: string;
  category?: string;
};

export type TAgentAssignmentApi = {
  id: string;
  workspace: string;
  project: string;
  work_item: string;
  agent_ref: string;
  assignment_type: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type TAgentRunApi = {
  id: string;
  workspace: string;
  project: string;
  assignment: string;
  agent_ref: string;
  model_used: string;
  outcome: string;
  progression_outcome?: string | null;
  started_at: string;
  completed_at?: string | null;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number | string;
  correlation_id?: string;
  created_at: string;
  updated_at: string;
};

export type TAgentAttentionItemApi = {
  id: string;
  workspace: string;
  project: string;
  entity_type: string;
  entity_id: string;
  drift_type: string;
  details: Record<string, unknown>;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type TAgentSyncStatusApi = {
  pending_outbox_count: number;
  last_outbox_delivery_at?: string | null;
  stale_assignment_count: number;
  orphaned_run_count: number;
  last_reconciliation_at?: string | null;
};

export type TAgentRunDetailApi = TAgentRunApi & {
  progression_outcome?: string | null;
  progression_reason?: string;
  progression_evaluated_at?: string | null;
  authorizing_review?: {
    id: string;
    reviewer_agent_ref: string;
    reviewer_model: string;
    verdict: string;
    reason: string;
    reviewed_at: string;
  } | null;
  review_disposition?: {
    id: string;
    reviewer: string;
    disposition: string;
    reason: string;
    reviewed_at: string;
  } | null;
  artifact_references: Array<{
    id: string;
    artifact_type: string;
    storage_ref: string;
    hash: string;
    classification: string;
    expires_at?: string | null;
  }>;
  context_manifests: Array<{
    id: string;
    knowledge_version_id: string;
    source_name?: string;
    version_number: number;
    bound_at?: string;
  }>;
  assignment_summary: {
    id: string;
    agent_ref: string;
    assignment_type: string;
    status: string;
    work_item_id: string;
  };
};

export type TRunLedgerItemApi = TAgentRunApi & {
  progression_outcome?: string | null;
  verdict?: string | null;
  disposition?: string | null;
  work_item_id?: string | null;
};

export type TRunLedgerParams = TAgentInfraListParams & {
  outcome?: string;
  progression_outcome?: string;
  agent_ref?: string;
  assignment_id?: string;
  work_item_id?: string;
};

export type TCreateDispositionPayload = {
  disposition: "approved" | "rejected" | "rework";
  reason: string;
  reviewed_at: string;
};

// --- P7: Authorization Policy API types ---

export type TAuthorizationPolicyApi = {
  id: string;
  workspace: string;
  project?: string | null;
  name: string;
  version: string;
  description: string;
  scope: string;
  priority: number;
  effect: string;
  subjects: Array<{ type: string; ref: string; conditions?: Record<string, unknown> | null }>;
  resources: Array<{ type: string; ref: string; conditions?: Record<string, unknown> | null }>;
  actions: string[];
  conditions?: Record<string, unknown> | null;
  separation_of_duty?: Array<{
    name: string;
    description: string;
    conflicting_actions: string[];
    scope: string;
  }> | null;
  autonomy_classification: string;
  emergency: boolean;
  status: string;
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

export type TAuthorizationPolicyListApi = {
  id: string;
  name: string;
  version: string;
  description: string;
  scope: string;
  priority: number;
  effect: string;
  autonomy_classification: string;
  emergency: boolean;
  status: string;
  revision_number: number;
  owner: string;
  created_at: string;
  updated_at: string;
};

export type TPolicyDecisionApi = {
  id: string;
  workspace: string;
  project?: string | null;
  subject_type: string;
  subject_ref: string;
  resource_type: string;
  resource_ref: string;
  action: string;
  outcome: string;
  matching_policies: string[];
  deciding_policy?: string | null;
  evaluation_context: Record<string, unknown>;
  reason: string;
  evaluated_at: string;
  correlation_id?: string;
  run?: string | null;
  created_at: string;
};

export type TActionApprovalApi = {
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
  status: string;
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

export type TEmergencyDenyApi = {
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

export type TSeparationOfDutyConstraintApi = {
  id: string;
  workspace: string;
  project?: string | null;
  policy: string;
  name: string;
  description: string;
  conflicting_actions: string[];
  scope: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TPolicyListParams = TAgentInfraListParams & {
  effect?: string;
  scope?: string;
  emergency?: string;
};

export type TApprovalListParams = TAgentInfraListParams & {
  status?: string;
};

export type TEmergencyDenyListParams = {
  active?: string;
};

export type TPolicySimulatePayload = {
  subject_type: string;
  subject_ref: string;
  resource_type: string;
  resource_ref: string;
  action: string;
  context?: Record<string, unknown>;
};

export type TPolicyDiffPayload = {
  policy_a_id: string;
  policy_b_id: string;
};

export type TPolicyBlastRadiusPayload = {
  policy_id: string;
};

export type TApprovalReviewPayload = {
  status: "approved" | "rejected";
  reason?: string;
};

export class AgentInfraService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private projectBasePath(workspaceSlug: string, projectId: string) {
    return `/api/v1/workspaces/${workspaceSlug}/projects/${projectId}`;
  }

  async fetchAssignments(
    workspaceSlug: string,
    projectId: string,
    params?: TAgentInfraListParams
  ): Promise<TAgentInfraPaginatedResponse<TAgentAssignmentApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/agent-assignments/`, {
      params,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchRuns(
    workspaceSlug: string,
    projectId: string,
    params?: TAgentInfraListParams
  ): Promise<TAgentInfraPaginatedResponse<TAgentRunApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/agent-runs/`, {
      params,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchAttentionItems(
    workspaceSlug: string,
    projectId: string,
    params?: TAgentInfraListParams
  ): Promise<TAgentInfraPaginatedResponse<TAgentAttentionItemApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/agent-attention-items/`, {
      params,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchSyncStatus(workspaceSlug: string, projectId: string): Promise<TAgentSyncStatusApi> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/agent-sync-status/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async resolveAttentionItem(
    workspaceSlug: string,
    projectId: string,
    itemId: string
  ): Promise<TAgentAttentionItemApi> {
    return this.patch(`${this.projectBasePath(workspaceSlug, projectId)}/agent-attention-items/${itemId}/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchRunDetail(workspaceSlug: string, projectId: string, runId: string): Promise<TAgentRunDetailApi> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/agent-runs/${runId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchRunLedger(
    workspaceSlug: string,
    projectId: string,
    params?: TRunLedgerParams
  ): Promise<TAgentInfraPaginatedResponse<TRunLedgerItemApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/agent-runs/ledger/`, {
      params,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async createDisposition(
    workspaceSlug: string,
    projectId: string,
    runId: string,
    payload: TCreateDispositionPayload
  ): Promise<unknown> {
    return this.post(
      `${this.projectBasePath(workspaceSlug, projectId)}/agent-runs/${runId}/review-dispositions/`,
      payload
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  getArtifactDownloadUrl(workspaceSlug: string, projectId: string, runId: string, artifactId: string): string {
    return `${API_BASE_URL}${this.projectBasePath(workspaceSlug, projectId)}/agent-runs/${runId}/artifact-references/${artifactId}/download/`;
  }

  // --- P7: Authorization Policy methods ---

  async fetchPolicies(
    workspaceSlug: string,
    projectId: string,
    params?: TPolicyListParams
  ): Promise<TAgentInfraPaginatedResponse<TAuthorizationPolicyListApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/`, { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async createPolicy(
    workspaceSlug: string,
    projectId: string,
    payload: Partial<TAuthorizationPolicyApi>
  ): Promise<TAuthorizationPolicyApi> {
    return this.post(`${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchPolicy(workspaceSlug: string, projectId: string, policyId: string): Promise<TAuthorizationPolicyApi> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/${policyId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async updatePolicy(
    workspaceSlug: string,
    projectId: string,
    policyId: string,
    payload: Partial<TAuthorizationPolicyApi>
  ): Promise<TAuthorizationPolicyApi> {
    return this.patch(`${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/${policyId}/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async approvePolicy(workspaceSlug: string, projectId: string, policyId: string): Promise<TAuthorizationPolicyApi> {
    return this.post(
      `${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/${policyId}/approve/`,
      {}
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async revokePolicy(
    workspaceSlug: string,
    projectId: string,
    policyId: string,
    reason: string
  ): Promise<TAuthorizationPolicyApi> {
    return this.post(`${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/${policyId}/revoke/`, {
      reason,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async simulatePolicy(workspaceSlug: string, projectId: string, payload: TPolicySimulatePayload): Promise<unknown> {
    return this.post(`${this.projectBasePath(workspaceSlug, projectId)}/policy-simulate/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async diffPolicies(
    workspaceSlug: string,
    projectId: string,
    policyId: string,
    payload: { compare_with: string }
  ): Promise<unknown> {
    return this.post(
      `${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/${policyId}/diff/`,
      payload
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async blastRadius(workspaceSlug: string, projectId: string, policyId: string): Promise<unknown> {
    return this.post(
      `${this.projectBasePath(workspaceSlug, projectId)}/authorization-policies/${policyId}/blast-radius/`,
      {}
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchDecisions(
    workspaceSlug: string,
    projectId: string,
    params?: TAgentInfraListParams
  ): Promise<TAgentInfraPaginatedResponse<TPolicyDecisionApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/policy-decisions/`, { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchApprovals(
    workspaceSlug: string,
    projectId: string,
    params?: TApprovalListParams
  ): Promise<TAgentInfraPaginatedResponse<TActionApprovalApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/action-approvals/`, { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchApproval(workspaceSlug: string, projectId: string, approvalId: string): Promise<TActionApprovalApi> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/action-approvals/${approvalId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async reviewApproval(
    workspaceSlug: string,
    projectId: string,
    approvalId: string,
    payload: TApprovalReviewPayload
  ): Promise<TActionApprovalApi> {
    return this.patch(`${this.projectBasePath(workspaceSlug, projectId)}/action-approvals/${approvalId}/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchEmergencyDenies(
    workspaceSlug: string,
    projectId: string,
    params?: TEmergencyDenyListParams
  ): Promise<TAgentInfraPaginatedResponse<TEmergencyDenyApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/emergency-denies/`, { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async activateEmergencyDeny(
    workspaceSlug: string,
    projectId: string,
    payload: { reason: string; scope_filter?: Record<string, unknown>; incident_reference?: string }
  ): Promise<TEmergencyDenyApi> {
    return this.post(`${this.projectBasePath(workspaceSlug, projectId)}/emergency-denies/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async deactivateEmergencyDeny(
    workspaceSlug: string,
    projectId: string,
    emergencyId: string,
    reason: string
  ): Promise<TEmergencyDenyApi> {
    return this.post(`${this.projectBasePath(workspaceSlug, projectId)}/emergency-denies/${emergencyId}/deactivate/`, {
      reason,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async fetchSoDConstraints(
    workspaceSlug: string,
    projectId: string
  ): Promise<TAgentInfraPaginatedResponse<TSeparationOfDutyConstraintApi>> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/sod-constraints/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }
}

const agentInfraService = new AgentInfraService();

export default agentInfraService;
