# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views import (
    AgentAssignmentDetailAPIEndpoint,
    AgentAssignmentListCreateAPIEndpoint,
    AgentCatalogAPIEndpoint,
    AgentInfraAttentionItemDetailAPIEndpoint,
    AgentInfraAttentionItemListAPIEndpoint,
    AgentRunDetailAPIEndpoint,
    AgentRunListCreateAPIEndpoint,
    AgentSyncStatusAPIEndpoint,
    ArtifactReferenceListCreateAPIEndpoint,
    AuthorizingReviewListCreateAPIEndpoint,
    ReviewDispositionListCreateAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-assignments/",
        AgentAssignmentListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="agent-assignment",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-assignments/<uuid:assignment_id>/",
        AgentAssignmentDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="agent-assignment",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-runs/",
        AgentRunListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="agent-run",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-runs/<uuid:run_id>/",
        AgentRunDetailAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-run",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-runs/<uuid:run_id>/authorizing-reviews/",
        AuthorizingReviewListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="authorizing-review",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-runs/<uuid:run_id>/artifact-references/",
        ArtifactReferenceListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="artifact-reference",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-runs/<uuid:run_id>/review-dispositions/",
        ReviewDispositionListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="review-disposition",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-catalog/",
        AgentCatalogAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-catalog",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-attention-items/",
        AgentInfraAttentionItemListAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-attention-item",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-attention-items/<uuid:attention_item_id>/",
        AgentInfraAttentionItemDetailAPIEndpoint.as_view(http_method_names=["patch"]),
        name="agent-attention-item",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-sync-status/",
        AgentSyncStatusAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-sync-status",
    ),
]
