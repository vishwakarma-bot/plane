/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  AgentEntry,
  EnvironmentEntry,
  IntegrationEntry,
  ModelEntry,
  SkillEntry,
} from "@/components/agent-infra/workforce/workforce-types";
import type {
  TEnvironmentRevision,
  TIntegrationRegistration,
  TModelRoutingConfig,
  TProjectAgentEnablement,
  TCompatibilityRecord,
} from "@/components/agent-infra/governance-types";
import { APIService } from "@/services/api.service";

type TCatalogListResponse<T> =
  | T[]
  | { results?: T[]; items?: T[]; agents?: T[]; skills?: T[]; models?: T[]; environments?: T[]; integrations?: T[] };

function extractList<T>(data: TCatalogListResponse<T> | undefined, keys: string[]): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;

  for (const key of keys) {
    const value = (data as Record<string, unknown>)[key];
    if (Array.isArray(value)) return value as T[];
  }

  if (Array.isArray(data.results)) return data.results;
  return [];
}

export class CatalogService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private projectBasePath(workspaceSlug: string, projectId: string) {
    return `/api/v1/workspaces/${workspaceSlug}/projects/${projectId}/agent-catalog`;
  }

  async getCatalog(workspaceSlug: string, projectId: string) {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getWorkforce(workspaceSlug: string, projectId: string): Promise<AgentEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/workforce/`)
      .then((response) => extractList<AgentEntry>(response?.data, ["items", "agents", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getSkills(workspaceSlug: string, projectId: string): Promise<SkillEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/skills/`)
      .then((response) => extractList<SkillEntry>(response?.data, ["items", "skills", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getModels(workspaceSlug: string, projectId: string): Promise<ModelEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/models/`)
      .then((response) => extractList<ModelEntry>(response?.data, ["items", "models", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getEnvironments(workspaceSlug: string, projectId: string): Promise<EnvironmentEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/environments/`)
      .then((response) => extractList<EnvironmentEntry>(response?.data, ["items", "environments", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getIntegrations(workspaceSlug: string, projectId: string): Promise<IntegrationEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/integrations/`)
      .then((response) => extractList<IntegrationEntry>(response?.data, ["items", "integrations", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  private governanceBasePath(workspaceSlug: string, projectId: string) {
    return `/api/v1/workspaces/${workspaceSlug}/projects/${projectId}`;
  }

  async getEnablements(workspaceSlug: string, projectId: string): Promise<TProjectAgentEnablement[]> {
    return this.get(`${this.governanceBasePath(workspaceSlug, projectId)}/agent-enablements/`)
      .then((response) => extractList<TProjectAgentEnablement>(response?.data, ["results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async createEnablement(workspaceSlug: string, projectId: string, data: Partial<TProjectAgentEnablement>) {
    return this.post(`${this.governanceBasePath(workspaceSlug, projectId)}/agent-enablements/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async updateEnablement(
    workspaceSlug: string,
    projectId: string,
    enablementId: string,
    data: Partial<TProjectAgentEnablement>
  ) {
    return this.patch(`${this.governanceBasePath(workspaceSlug, projectId)}/agent-enablements/${enablementId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async deleteEnablement(workspaceSlug: string, projectId: string, enablementId: string) {
    return this.delete(`${this.governanceBasePath(workspaceSlug, projectId)}/agent-enablements/${enablementId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async checkCompatibility(
    workspaceSlug: string,
    projectId: string,
    sourceType: string,
    sourceRef: string,
    targetType: string,
    targetRef: string
  ): Promise<TCompatibilityRecord> {
    return this.get(`${this.governanceBasePath(workspaceSlug, projectId)}/compatibility-checks/`, {
      params: { source_type: sourceType, source_ref: sourceRef, target_type: targetType, target_ref: targetRef },
    })
      .then((response) => {
        const data = response?.data;
        if (Array.isArray(data?.results) && data.results.length > 0) return data.results[0];
        if (Array.isArray(data) && data.length > 0) return data[0];
        return data;
      })
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getEnvironmentRevisions(workspaceSlug: string, projectId: string): Promise<TEnvironmentRevision[]> {
    return this.get(`${this.governanceBasePath(workspaceSlug, projectId)}/environment-revisions/`)
      .then((response) => extractList<TEnvironmentRevision>(response?.data, ["results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async triggerDriftCheck(workspaceSlug: string, projectId: string, revisionId: string) {
    return this.post(
      `${this.governanceBasePath(workspaceSlug, projectId)}/environment-revisions/${revisionId}/drift-check/`,
      {}
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getIntegrationRegistrations(workspaceSlug: string, projectId: string): Promise<TIntegrationRegistration[]> {
    return this.get(`${this.governanceBasePath(workspaceSlug, projectId)}/integration-registrations/`)
      .then((response) => extractList<TIntegrationRegistration>(response?.data, ["results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getModelRouting(workspaceSlug: string, projectId: string): Promise<TModelRoutingConfig[]> {
    return this.get(`${this.governanceBasePath(workspaceSlug, projectId)}/model-routing-configs/`)
      .then((response) => extractList<TModelRoutingConfig>(response?.data, ["results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async updateModelRouting(
    workspaceSlug: string,
    projectId: string,
    configId: string,
    data: Partial<TModelRoutingConfig>
  ) {
    return this.patch(`${this.governanceBasePath(workspaceSlug, projectId)}/model-routing-configs/${configId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async approveCatalogRevision(workspaceSlug: string, projectId: string, revisionId: string) {
    return this.post(`${this.governanceBasePath(workspaceSlug, projectId)}/catalog-revisions/${revisionId}/approve/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async rejectCatalogRevision(workspaceSlug: string, projectId: string, revisionId: string, reason?: string) {
    return this.post(`${this.governanceBasePath(workspaceSlug, projectId)}/catalog-revisions/${revisionId}/reject/`, {
      reason,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async rollbackCatalogRevision(workspaceSlug: string, projectId: string, revisionId: string) {
    return this.post(`${this.governanceBasePath(workspaceSlug, projectId)}/catalog-revisions/${revisionId}/rollback/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }
}

const catalogService = new CatalogService();

export default catalogService;
