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
}

const agentInfraService = new AgentInfraService();

export default agentInfraService;
