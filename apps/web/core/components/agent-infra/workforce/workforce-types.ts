/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export interface AgentEntry {
  name: string;
  description?: string;
  model_preference?: string;
  assignment_types?: string[];
  skills?: string[];
  status: "ok" | "error";
  path: string;
  content_hash: string;
  validation_errors?: string[];
}

export interface SkillEntry {
  name: string;
  description?: string;
  type?: string;
  summary?: string;
  status: "ok" | "error";
  path: string;
  content_hash: string;
  validation_errors?: string[];
}

export interface ModelEntry {
  name: string;
  provider?: string;
  capabilities?: string[];
  data_region?: string;
  cost_per_1k_input?: number;
  cost_per_1k_output?: number;
  max_context_tokens?: number;
  routing_priority?: number;
  shadow_mode?: boolean;
  status: "ok" | "error";
  path: string;
  content_hash: string;
  validation_errors?: string[];
}

export interface EnvironmentEntry {
  name: string;
  description?: string;
  toolchain?: string[];
  capabilities?: string[];
  status: "ok" | "error";
  path: string;
  content_hash: string;
  validation_errors?: string[];
}

export interface IntegrationEntry {
  name: string;
  type?: string;
  description?: string;
  tools?: string[];
  scopes?: string[];
  approval_class?: string;
  status: "ok" | "error" | "active" | "disabled" | "deprecated";
  path: string;
  content_hash: string;
  validation_errors?: string[];
}
