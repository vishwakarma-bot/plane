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
import { APIService } from "@/services/api.service";

type TCatalogListResponse<T> = T[] | { results?: T[]; agents?: T[]; skills?: T[]; models?: T[]; environments?: T[]; integrations?: T[] };

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
      .then((response) => extractList<AgentEntry>(response?.data, ["agents", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getSkills(workspaceSlug: string, projectId: string): Promise<SkillEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/skills/`)
      .then((response) => extractList<SkillEntry>(response?.data, ["skills", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getModels(workspaceSlug: string, projectId: string): Promise<ModelEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/models/`)
      .then((response) => extractList<ModelEntry>(response?.data, ["models", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getEnvironments(workspaceSlug: string, projectId: string): Promise<EnvironmentEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/environments/`)
      .then((response) => extractList<EnvironmentEntry>(response?.data, ["environments", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getIntegrations(workspaceSlug: string, projectId: string): Promise<IntegrationEntry[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/integrations/`)
      .then((response) => extractList<IntegrationEntry>(response?.data, ["integrations", "results"]))
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }
}

const catalogService = new CatalogService();

export default catalogService;
