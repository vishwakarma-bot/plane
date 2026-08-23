/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TCatalogStatus = "ok" | "error" | "active" | "disabled" | "deprecated";

export const CATALOG_STATUS_BADGE_CLASSES: Record<TCatalogStatus, string> = {
  ok: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  active: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  disabled: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  deprecated: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
};

export function truncateContentHash(hash?: string): string {
  if (!hash) return "—";
  return hash.slice(0, 8);
}

export function formatCost(value?: number): string {
  if (value === undefined || value === null) return "—";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return "—";
  return `$${num.toFixed(4)}`;
}

export function safeStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  if (typeof value === "string") return [value];
  return [];
}

export function formatTokenCount(value?: number): string {
  if (value === undefined || value === null) return "—";
  return String(value);
}
