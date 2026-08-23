/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import type {
  TContextManifest,
  TKnowledgeSource,
  TKnowledgeVersion,
} from "@/components/agent-infra/knowledge/knowledge-types";
import knowledgeService from "@/services/knowledge.service";

const swrOptions = {
  revalidateOnFocus: false,
  shouldRetryOnError: false,
};

function buildKey(prefix: string, ...parts: (string | undefined)[]) {
  const filtered = parts.filter(Boolean);
  return filtered.length === parts.length ? `${prefix}_${filtered.join("_")}` : null;
}

export function useKnowledgeSources(workspaceSlug?: string, projectId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("KNOWLEDGE_SOURCES", workspaceSlug, projectId),
    workspaceSlug && projectId ? () => knowledgeService.listSources(workspaceSlug, projectId) : null,
    swrOptions
  );

  return {
    sources: data as TKnowledgeSource[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId) && isLoading,
    error,
    mutate,
  };
}

export function useKnowledgeSource(workspaceSlug?: string, projectId?: string, sourceId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("KNOWLEDGE_SOURCE", workspaceSlug, projectId, sourceId),
    workspaceSlug && projectId && sourceId
      ? () => knowledgeService.getSource(workspaceSlug, projectId, sourceId)
      : null,
    swrOptions
  );

  return {
    source: data as TKnowledgeSource | undefined,
    isLoading: Boolean(workspaceSlug && projectId && sourceId) && isLoading,
    error,
    mutate,
  };
}

export function useKnowledgeVersions(workspaceSlug?: string, projectId?: string, sourceId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("KNOWLEDGE_VERSIONS", workspaceSlug, projectId, sourceId),
    workspaceSlug && projectId && sourceId
      ? () => knowledgeService.listVersions(workspaceSlug, projectId, sourceId)
      : null,
    swrOptions
  );

  return {
    versions: data as TKnowledgeVersion[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId && sourceId) && isLoading,
    error,
    mutate,
  };
}

export function useContextManifests(workspaceSlug?: string, projectId?: string, runId?: string) {
  const { data, error, isLoading, mutate } = useSWR(
    buildKey("CONTEXT_MANIFESTS", workspaceSlug, projectId, runId),
    workspaceSlug && projectId && runId
      ? () => knowledgeService.listManifests(workspaceSlug, projectId, runId)
      : null,
    swrOptions
  );

  return {
    manifests: data as TContextManifest[] | undefined,
    isLoading: Boolean(workspaceSlug && projectId && runId) && isLoading,
    error,
    mutate,
  };
}
