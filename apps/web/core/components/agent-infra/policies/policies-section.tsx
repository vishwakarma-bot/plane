/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Loader } from "@plane/ui";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { useAuthorizationPolicies } from "@/hooks/use-agent-infra";
import type { TAuthorizationPolicyListItem } from "../governance-types";
import { PolicyDetail } from "./policy-detail";
import { PolicyList } from "./policy-list";
import { PolicySimulator } from "./policy-simulator";

type TPoliciesSectionProps = {
  workspaceSlug: string;
  projectId: string;
};

export function PoliciesSection(props: TPoliciesSectionProps) {
  const { workspaceSlug, projectId } = props;
  const { policies, isLoading, error, mutate } = useAuthorizationPolicies(workspaceSlug, projectId);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);

  if (error) {
    return (
      <div className="grid place-items-center rounded-lg border border-subtle bg-surface-1 px-6 py-16">
        <EmptyStateDetailed
          title="Failed to load policies"
          description="Could not fetch authorization policies. Please try again."
          assetKey="project"
          assetClassName="size-32"
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <Loader className="space-y-4">
        <Loader.Item height="48px" />
        <Loader.Item height="280px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PolicyList
        policies={policies as TAuthorizationPolicyListItem[] | undefined}
        selectedId={selectedPolicyId}
        onPolicySelect={setSelectedPolicyId}
      />
      {selectedPolicyId && (
        <PolicyDetail
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          policyId={selectedPolicyId}
          onMutate={() => mutate()}
        />
      )}
      <PolicySimulator workspaceSlug={workspaceSlug} projectId={projectId} />
    </div>
  );
}
