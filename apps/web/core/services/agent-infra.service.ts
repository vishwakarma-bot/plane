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
}

const agentInfraService = new AgentInfraService();

export default agentInfraService;
