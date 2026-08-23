/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TSourceType = "plane" | "repository" | "ci" | "incident" | "external";
export type TAuthorityType = "product" | "design" | "architecture" | "qa" | "security" | "platform" | "release";
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

export type TIndexAction = "index" | "reindex" | "delete";
export type TIndexRequestStatus = "pending" | "acknowledged" | "in_progress" | "completed" | "failed";

export interface TKnowledgeIndexRecord {
  id: string;
  knowledge_version: string;
  action: TIndexAction;
  status: TIndexRequestStatus;
  requested_at: string;
  acknowledged_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  failure_reason: string;
  retry_count: number;
  max_retries: number;
  external_ref: string;
  last_observed_at: string | null;
  is_verified: boolean;
}

export type TConflictStatus = "open" | "acknowledged" | "resolved" | "superseded";
export type TConflictType = "authority" | "semantic" | "staleness";

export interface TKnowledgeConflictRecord {
  id: string;
  version_a: string;
  version_b: string;
  conflict_type: TConflictType;
  status: TConflictStatus;
  description: string;
  resolution_summary: string;
  resolved_by: string | null;
  resolved_at: string | null;
  winning_version: string | null;
  blocks_execution: boolean;
  created_at: string;
}

export type TSourceLifecycleStatus = "active" | "expired" | "retired";

export type TStalenessLevel = "fresh" | "approaching" | "expired";

export type TKnowledgeConflict = {
  sourceId: string;
  sourceName: string;
  approvedVersions: TKnowledgeVersion[];
};
