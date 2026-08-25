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
import type {
  TEnvironmentRevision,
  TIntegrationRegistration,
  TModelRoutingConfig,
  TProjectAgentEnablement,
} from "@/components/agent-infra/governance-types";
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

export function useAgentEnablements(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("AGENT_ENABLEMENTS", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () => catalogService.getEnablements(workspaceSlug, projectId).catch(() => [] as TProjectAgentEnablement[])
      : null,
    swrOptions
  );

  return {
    enablements: data as TProjectAgentEnablement[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useEnvironmentRevisions(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("ENVIRONMENT_REVISIONS", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () => catalogService.getEnvironmentRevisions(workspaceSlug, projectId).catch(() => [] as TEnvironmentRevision[])
      : null,
    swrOptions
  );

  return {
    revisions: data as TEnvironmentRevision[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useIntegrationRegistrations(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("INTEGRATION_REGISTRATIONS", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () =>
          catalogService
            .getIntegrationRegistrations(workspaceSlug, projectId)
            .catch(() => [] as TIntegrationRegistration[])
      : null,
    swrOptions
  );

  return {
    registrations: data as TIntegrationRegistration[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useModelRouting(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("MODEL_ROUTING", workspaceSlug, projectId),
    workspaceSlug && projectId
      ? () => catalogService.getModelRouting(workspaceSlug, projectId).catch(() => [] as TModelRoutingConfig[])
      : null,
    swrOptions
  );

  return {
    configs: data as TModelRoutingConfig[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}
