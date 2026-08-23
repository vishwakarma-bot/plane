/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TBadgeVariant } from "@plane/ui";
import { Badge } from "@plane/ui";
import type { TAuthorizingReviewVerdict } from "./mock-data";
import { REVIEW_VERDICT_LABELS } from "./mock-data";

type TReviewBadgeProps = {
  verdict: TAuthorizingReviewVerdict;
  size?: "sm" | "md";
  className?: string;
};

const VERDICT_VARIANTS: Record<TAuthorizingReviewVerdict, TBadgeVariant> = {
  accepted: "accent-success",
  flagged: "accent-warning",
  escalated: "accent-destructive",
};

export function ReviewBadge(props: TReviewBadgeProps) {
  const { verdict, size = "sm", className = "" } = props;

  return (
    <Badge variant={VERDICT_VARIANTS[verdict]} size={size} className={className} disabled>
      {REVIEW_VERDICT_LABELS[verdict]}
    </Badge>
  );
}
