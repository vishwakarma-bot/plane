# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class ContextManifest(BaseModel):
    run = models.ForeignKey(
        "agent_infra.AgentRun",
        on_delete=models.CASCADE,
        related_name="context_manifests",
    )
    knowledge_version = models.ForeignKey(
        "agent_infra.KnowledgeVersion",
        on_delete=models.CASCADE,
        related_name="manifest_entries",
    )
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="context_manifests")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="context_manifests")
    bound_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Context Manifest"
        verbose_name_plural = "Context Manifests"
        db_table = "agent_infra_context_manifests"
        ordering = ("-bound_at",)
        unique_together = ("run", "knowledge_version")

    def __str__(self):
        return f"Manifest {self.run_id} -> {self.knowledge_version_id}"
