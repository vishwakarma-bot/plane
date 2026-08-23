/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Bot, Plus } from "lucide-react";
import { Button, CustomSelect, Loader } from "@plane/ui";
import { AssignmentCard } from "./assignment-card";
import type { TAgentAssignment, TAgentRef, TAssignmentType } from "./mock-data";
import {
  ASSIGNMENT_TYPE_LABELS,
  MOCK_AGENTS,
  MOCK_ASSIGNMENTS,
} from "./mock-data";

type TAssignmentPanelProps = {
  workItemId?: string;
  assignments?: TAgentAssignment[];
  agents?: TAgentRef[];
  isLoading?: boolean;
};

export function AssignmentPanel(props: TAssignmentPanelProps) {
  const {
    workItemId,
    assignments: assignmentsProp,
    agents = MOCK_AGENTS,
    isLoading = false,
  } = props;

  const [assignments, setAssignments] = useState<TAgentAssignment[]>(assignmentsProp ?? MOCK_ASSIGNMENTS);
  const [showAssignForm, setShowAssignForm] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [selectedType, setSelectedType] = useState<TAssignmentType>("dev");

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId);

  const handleAssignAgent = () => {
    if (!selectedAgent) return;

    const newAssignment: TAgentAssignment = {
      id: `asgn-${Date.now()}`,
      agentRef: selectedAgent.id,
      agentName: selectedAgent.name,
      assignmentType: selectedType,
      status: "pending",
      createdAt: new Date().toISOString(),
      runs: [],
    };

    setAssignments((prev) => [newAssignment, ...prev]);
    setSelectedAgentId("");
    setSelectedType("dev");
    setShowAssignForm(false);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 rounded-lg border border-subtle bg-surface-1 p-4">
        <div className="flex items-center justify-between">
          <Loader.Item height="16px" width="120px" />
          <Loader.Item height="28px" width="100px" />
        </div>
        <Loader className="space-y-3">
          <Loader.Item height="72px" />
          <Loader.Item height="72px" />
        </Loader>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-accent-primary" />
          <div>
            <h3 className="text-14 font-semibold text-primary">Agent assignments</h3>
            {workItemId && <p className="text-11 text-tertiary">Work item {workItemId}</p>}
          </div>
        </div>
        <Button
          variant="outline-primary"
          size="sm"
          prependIcon={<Plus className="h-3 w-3" />}
          onClick={() => setShowAssignForm((prev) => !prev)}
        >
          Assign agent
        </Button>
      </div>

      {showAssignForm && (
        <div className="rounded-md border border-subtle bg-layer-2 p-3">
          <div className="mb-3 text-13 font-medium text-secondary">New assignment</div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-1.5">
              <label className="text-11 font-medium text-tertiary">Agent</label>
              <CustomSelect
                value={selectedAgentId}
                onChange={(value) => setSelectedAgentId(value as string)}
                label={selectedAgent?.name ?? "Select agent"}
                buttonClassName="w-full"
              >
                {agents.map((agent) => (
                  <CustomSelect.Option key={agent.id} value={agent.id}>
                    <div className="flex flex-col">
                      <span>{agent.name}</span>
                      {agent.description && <span className="text-11 text-tertiary">{agent.description}</span>}
                    </div>
                  </CustomSelect.Option>
                ))}
              </CustomSelect>
            </div>
            <div className="w-full space-y-1.5 sm:w-40">
              <label className="text-11 font-medium text-tertiary">Type</label>
              <CustomSelect
                value={selectedType}
                onChange={(value) => setSelectedType(value as TAssignmentType)}
                label={ASSIGNMENT_TYPE_LABELS[selectedType]}
                buttonClassName="w-full"
              >
                {(Object.keys(ASSIGNMENT_TYPE_LABELS) as TAssignmentType[]).map((type) => (
                  <CustomSelect.Option key={type} value={type}>
                    {ASSIGNMENT_TYPE_LABELS[type]}
                  </CustomSelect.Option>
                ))}
              </CustomSelect>
            </div>
            <Button variant="primary" size="sm" disabled={!selectedAgentId} onClick={handleAssignAgent}>
              Assign
            </Button>
          </div>
        </div>
      )}

      {assignments.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-subtle px-4 py-8 text-center">
          <Bot className="h-8 w-8 text-tertiary" />
          <div>
            <p className="text-13 font-medium text-secondary">No agents assigned</p>
            <p className="mt-1 text-11 text-tertiary">
              Assign an agent to start automated work on this item.
            </p>
          </div>
          <Button variant="outline-primary" size="sm" onClick={() => setShowAssignForm(true)}>
            Assign your first agent
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {assignments.map((assignment, index) => (
            <AssignmentCard key={assignment.id} assignment={assignment} defaultExpanded={index === 0} />
          ))}
        </div>
      )}
    </div>
  );
}
