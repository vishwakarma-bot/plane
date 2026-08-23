/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { LucideIcon } from "lucide-react";
import { Card, ECardSpacing, ECardVariant, Loader } from "@plane/ui";

type TStatCardProps = {
  label: string;
  value: string | number;
  icon: LucideIcon;
  description?: string;
  isLoading?: boolean;
  trend?: {
    value: string;
    positive?: boolean;
  };
};

export function StatCard(props: TStatCardProps) {
  const { label, value, icon: Icon, description, isLoading = false, trend } = props;

  if (isLoading) {
    return (
      <Card
        variant={ECardVariant.WITHOUT_SHADOW}
        spacing={ECardSpacing.SM}
        className="border border-subtle bg-surface-1"
      >
        <Loader className="space-y-2">
          <Loader.Item height="12px" width="40%" />
          <Loader.Item height="24px" width="30%" />
          <Loader.Item height="10px" width="60%" />
        </Loader>
      </Card>
    );
  }

  return (
    <Card variant={ECardVariant.WITHOUT_SHADOW} spacing={ECardSpacing.SM} className="border border-subtle bg-surface-1">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-11 font-medium tracking-wide text-tertiary uppercase">{label}</span>
          <span className="text-24 font-semibold text-primary">{value}</span>
          {description && <span className="text-11 text-tertiary">{description}</span>}
          {trend && (
            <span className={`text-11 font-medium ${trend.positive ? "text-success-primary" : "text-danger-primary"}`}>
              {trend.value}
            </span>
          )}
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent-subtle">
          <Icon className="h-4 w-4 text-accent-primary" />
        </div>
      </div>
    </Card>
  );
}
