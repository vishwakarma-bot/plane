/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TPolicyEffect, TPolicyStatus } from "../governance-types";

export const POLICY_STATUS_BADGE: Record<TPolicyStatus, string> = {
  draft: "bg-layer-2 text-secondary",
  pending_approval: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300",
  active: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300",
  deprecated: "bg-layer-2 text-tertiary",
  revoked: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300",
};

export const POLICY_EFFECT_BADGE: Record<TPolicyEffect, string> = {
  allow: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300",
  deny: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300",
  require_approval: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300",
};

export const EFFECT_LABELS: Record<TPolicyEffect, string> = {
  allow: "Allow",
  deny: "Deny",
  require_approval: "Require Approval",
};

export const STATUS_LABELS: Record<TPolicyStatus, string> = {
  draft: "Draft",
  pending_approval: "Pending Approval",
  active: "Active",
  deprecated: "Deprecated",
  revoked: "Revoked",
};
