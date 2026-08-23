/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TSourceType = "plane" | "repository" | "ci" | "incident" | "external";
export type TAuthorityType =
  | "product"
  | "design"
  | "architecture"
  | "qa"
  | "security"
  | "platform"
  | "release";
export type TSensitivity = "public" | "internal" | "confidential" | "restricted";
export type TVersionStatus = "draft" | "review" | "approved" | "rejected" | "superseded" | "quarantined";

export interface TKnowledgeSource {
  id: string;
  name: string;
  source_type: TSourceType;
  authority_type: TAuthorityType;
  sensitivity: TSensitivity;
  url: string;
  owner: string | null;
  effective_from: string | null;
  expires_at: string | null;
  retention_days: number;
  is_retired: boolean;
  retired_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TKnowledgeVersion {
  id: string;
  source: string;
  version_number: number;
  status: TVersionStatus;
  content_hash: string;
  diff_summary: string;
  is_agent_generated: boolean;
  promoted_by: string | null;
  promoted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TContextManifest {
  id: string;
  run: string;
  knowledge_version: string;
  bound_at: string;
}

export type TSourceLifecycleStatus = "active" | "expired" | "retired";

export type TStalenessLevel = "fresh" | "approaching" | "expired";

export type TKnowledgeConflict = {
  sourceId: string;
  sourceName: string;
  approvedVersions: TKnowledgeVersion[];
};
