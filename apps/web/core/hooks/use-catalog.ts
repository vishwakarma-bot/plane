/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import type {
  AgentEntry,
  EnvironmentEntry,
  IntegrationEntry,
  ModelEntry,
  SkillEntry,
} from "@/components/agent-infra/workforce/workforce-types";
import catalogService from "@/services/catalog.service";

const swrOptions = {
  revalidateOnFocus: false,
  shouldRetryOnError: false,
};

function buildKey(prefix: string, ...parts: (string | undefined)[]) {
  const filtered = parts.filter(Boolean);
  return filtered.length === parts.length ? `${prefix}_${filtered.join("_")}` : null;
}

export function useCatalogWorkforce(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("CATALOG_WORKFORCE", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => catalogService.getWorkforce(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    agents: data as AgentEntry[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useCatalogSkills(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("CATALOG_SKILLS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => catalogService.getSkills(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    skills: data as SkillEntry[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useCatalogModels(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("CATALOG_MODELS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => catalogService.getModels(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    models: data as ModelEntry[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useCatalogEnvironments(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("CATALOG_ENVIRONMENTS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => catalogService.getEnvironments(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    environments: data as EnvironmentEntry[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useCatalogIntegrations(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("CATALOG_INTEGRATIONS", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => catalogService.getIntegrations(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    integrations: data as IntegrationEntry[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}
