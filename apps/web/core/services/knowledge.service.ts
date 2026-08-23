/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TContextManifest,
  TKnowledgeConflictRecord,
  TKnowledgeIndexRecord,
  TKnowledgeSource,
  TKnowledgeVersion,
  TVersionStatus,
} from "@/components/agent-infra/knowledge/knowledge-types";
import { APIService } from "@/services/api.service";

export type TKnowledgePaginatedResponse<T> = {
  results: T[];
  count?: number;
  next_cursor?: string | null;
  prev_cursor?: string | null;
};

export class KnowledgeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private projectBasePath(workspaceSlug: string, projectId: string) {
    return `/api/v1/workspaces/${workspaceSlug}/projects/${projectId}`;
  }

  async listSources(workspaceSlug: string, projectId: string): Promise<TKnowledgeSource[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/`)
      .then((response) => (response?.data as TKnowledgePaginatedResponse<TKnowledgeSource>)?.results ?? [])
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async getSource(workspaceSlug: string, projectId: string, sourceId: string): Promise<TKnowledgeSource> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/${sourceId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async createSource(
    workspaceSlug: string,
    projectId: string,
    data: Partial<TKnowledgeSource>
  ): Promise<TKnowledgeSource> {
    return this.post(`${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async updateSource(
    workspaceSlug: string,
    projectId: string,
    sourceId: string,
    data: Partial<TKnowledgeSource>
  ): Promise<TKnowledgeSource> {
    return this.patch(`${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/${sourceId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async retireSource(workspaceSlug: string, projectId: string, sourceId: string): Promise<void> {
    return this.delete(`${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/${sourceId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async listVersions(
    workspaceSlug: string,
    projectId: string,
    sourceId: string
  ): Promise<TKnowledgeVersion[]> {
    return this.get(
      `${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/${sourceId}/versions/`
    )
      .then((response) => (response?.data as TKnowledgePaginatedResponse<TKnowledgeVersion>)?.results ?? [])
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async createVersion(
    workspaceSlug: string,
    projectId: string,
    sourceId: string,
    data: Partial<TKnowledgeVersion>
  ): Promise<TKnowledgeVersion> {
    return this.post(
      `${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/${sourceId}/versions/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async updateVersionStatus(
    workspaceSlug: string,
    projectId: string,
    sourceId: string,
    versionId: string,
    status: TVersionStatus
  ): Promise<TKnowledgeVersion> {
    return this.patch(
      `${this.projectBasePath(workspaceSlug, projectId)}/knowledge-sources/${sourceId}/versions/${versionId}/`,
      { status }
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async listManifests(
    workspaceSlug: string,
    projectId: string,
    runId: string
  ): Promise<TContextManifest[]> {
    return this.get(`${this.projectBasePath(workspaceSlug, projectId)}/agent-runs/${runId}/context-manifests/`)
      .then((response) => (response?.data as TKnowledgePaginatedResponse<TContextManifest>)?.results ?? [])
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async listIndexRecords(
    workspaceSlug: string,
    projectId: string,
    filterStatus?: string
  ): Promise<TKnowledgeIndexRecord[]> {
    const params = filterStatus ? `?status=${filterStatus}` : "";
    return this.get(
      `${this.projectBasePath(workspaceSlug, projectId)}/knowledge-index-records/${params}`
    )
      .then((response) => (response?.data as TKnowledgePaginatedResponse<TKnowledgeIndexRecord>)?.results ?? [])
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async createIndexRecord(
    workspaceSlug: string,
    projectId: string,
    data: { knowledge_version: string; action: string }
  ): Promise<TKnowledgeIndexRecord> {
    return this.post(
      `${this.projectBasePath(workspaceSlug, projectId)}/knowledge-index-records/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async listConflicts(
    workspaceSlug: string,
    projectId: string,
    filterStatus?: string
  ): Promise<TKnowledgeConflictRecord[]> {
    const params = filterStatus ? `?status=${filterStatus}` : "";
    return this.get(
      `${this.projectBasePath(workspaceSlug, projectId)}/knowledge-conflicts/${params}`
    )
      .then((response) => (response?.data as TKnowledgePaginatedResponse<TKnowledgeConflictRecord>)?.results ?? [])
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  async resolveConflict(
    workspaceSlug: string,
    projectId: string,
    conflictId: string,
    data: { status: string; resolution_summary: string; winning_version?: string }
  ): Promise<TKnowledgeConflictRecord> {
    return this.patch(
      `${this.projectBasePath(workspaceSlug, projectId)}/knowledge-conflicts/${conflictId}/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }
}

const knowledgeService = new KnowledgeService();

export default knowledgeService;
