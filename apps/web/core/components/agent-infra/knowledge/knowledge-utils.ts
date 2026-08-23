/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  TAuthorityType,
  TKnowledgeConflict,
  TKnowledgeSource,
  TKnowledgeVersion,
  TSourceLifecycleStatus,
  TStalenessLevel,
} from "./knowledge-types";

const APPROACHING_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000;

export const AUTHORITY_BADGE_CLASSES: Record<TAuthorityType, string> = {
  product: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  design: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  architecture: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  qa: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  security: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  platform: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  release: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
};

export const STALENESS_DOT_CLASSES: Record<TStalenessLevel, string> = {
  fresh: "bg-green-500",
  approaching: "bg-amber-500",
  expired: "bg-red-500",
};

export function getSourceLifecycleStatus(source: TKnowledgeSource): TSourceLifecycleStatus {
  if (source.is_retired) return "retired";
  if (source.expires_at && new Date(source.expires_at).getTime() <= Date.now()) return "expired";
  return "active";
}

export function getStalenessLevel(source: TKnowledgeSource): TStalenessLevel {
  if (source.is_retired) return "expired";
  if (!source.expires_at) return "fresh";

  const expiresAtMs = new Date(source.expires_at).getTime();
  const now = Date.now();

  if (expiresAtMs <= now) return "expired";
  if (expiresAtMs - now <= APPROACHING_EXPIRY_MS) return "approaching";
  return "fresh";
}

export function truncateHash(hash: string, length = 8): string {
  if (hash.length <= length * 2 + 3) return hash;
  return `${hash.slice(0, length)}…${hash.slice(-length)}`;
}

export function detectKnowledgeConflicts(
  sources: TKnowledgeSource[],
  versionsBySource: Record<string, TKnowledgeVersion[]>
): TKnowledgeConflict[] {
  return sources.flatMap((source) => {
    const approvedVersions = (versionsBySource[source.id] ?? []).filter((version) => version.status === "approved");

    if (approvedVersions.length < 2) return [];

    return [
      {
        sourceId: source.id,
        sourceName: source.name,
        approvedVersions,
      },
    ];
  });
}

export function getStaleSources(sources: TKnowledgeSource[]): TKnowledgeSource[] {
  return sources.filter((source) => {
    const staleness = getStalenessLevel(source);
    return staleness === "approaching" || staleness === "expired";
  });
}

/**
 * SSR-safe date formatters — produce identical output on server and client
 * by using UTC and manual formatting instead of locale-dependent Intl APIs.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "—";
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "—";
  return `${formatDate(value)} ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}
