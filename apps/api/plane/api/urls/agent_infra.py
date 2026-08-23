# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views import (
    AgentAssignmentDetailAPIEndpoint,
    AgentAssignmentListCreateAPIEndpoint,
    AgentCatalogAPIEndpoint,
    AgentCatalogEnvironmentsAPIEndpoint,
    AgentCatalogIntegrationsAPIEndpoint,
    AgentCatalogModelsAPIEndpoint,
    AgentCatalogSkillsAPIEndpoint,
    AgentCatalogWorkforceAPIEndpoint,
    AgentInfraAttentionItemDetailAPIEndpoint,
    AgentInfraAttentionItemListAPIEndpoint,
    AgentRunDetailAPIEndpoint,
    AgentRunListCreateAPIEndpoint,
    AgentSyncStatusAPIEndpoint,
    ArtifactReferenceListCreateAPIEndpoint,
    AuthorizingReviewListCreateAPIEndpoint,
    ContextManifestListCreateAPIEndpoint,
    KnowledgeSourceDetailAPIEndpoint,
    KnowledgeSourceListCreateAPIEndpoint,
    KnowledgeVersionDetailAPIEndpoint,
    KnowledgeVersionListCreateAPIEndpoint,
    ReviewDispositionListCreateAPIEndpoint,
    ProjectAgentEnablementListCreateAPIEndpoint,
    ProjectAgentEnablementDetailAPIEndpoint,
    ModelRoutingConfigListCreateAPIEndpoint,
    ModelRoutingConfigDetailAPIEndpoint,
    EnvironmentRevisionListCreateAPIEndpoint,
    EnvironmentRevisionDetailAPIEndpoint,
    EnvironmentDriftCheckAPIEndpoint,
    IntegrationRegistrationListCreateAPIEndpoint,
    IntegrationRegistrationDetailAPIEndpoint,
    CatalogRevisionListCreateAPIEndpoint,
    CatalogRevisionDetailAPIEndpoint,
    CatalogRevisionApproveAPIEndpoint,
    CatalogRevisionRejectAPIEndpoint,
    CatalogRevisionRollbackAPIEndpoint,
    CompatibilityCheckAPIEndpoint,
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
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-catalog/workforce/",
        AgentCatalogWorkforceAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-catalog-workforce",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-catalog/skills/",
        AgentCatalogSkillsAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-catalog-skills",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-catalog/models/",
        AgentCatalogModelsAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-catalog-models",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-catalog/environments/",
        AgentCatalogEnvironmentsAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-catalog-environments",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-catalog/integrations/",
        AgentCatalogIntegrationsAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-catalog-integrations",
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
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/knowledge-sources/",
        KnowledgeSourceListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="knowledge-source",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/knowledge-sources/<uuid:source_id>/",
        KnowledgeSourceDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="knowledge-source",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/knowledge-sources/<uuid:source_id>/versions/",
        KnowledgeVersionListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="knowledge-version",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/knowledge-sources/<uuid:source_id>/versions/<uuid:version_id>/",
        KnowledgeVersionDetailAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="knowledge-version",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-runs/<uuid:run_id>/context-manifests/",
        ContextManifestListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="context-manifest",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-enablements/",
        ProjectAgentEnablementListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="project-agent-enablement",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-enablements/<uuid:enablement_id>/",
        ProjectAgentEnablementDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="project-agent-enablement",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/model-routing-configs/",
        ModelRoutingConfigListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="model-routing-config",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/model-routing-configs/<uuid:routing_config_id>/",
        ModelRoutingConfigDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="model-routing-config",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/environment-revisions/",
        EnvironmentRevisionListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="environment-revision",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/environment-revisions/<uuid:revision_id>/",
        EnvironmentRevisionDetailAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="environment-revision",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/environment-revisions/<uuid:revision_id>/drift-check/",
        EnvironmentDriftCheckAPIEndpoint.as_view(http_method_names=["post"]),
        name="environment-drift-check",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/integration-registrations/",
        IntegrationRegistrationListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="integration-registration",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/integration-registrations/<uuid:registration_id>/",
        IntegrationRegistrationDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="integration-registration",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/catalog-revisions/",
        CatalogRevisionListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="catalog-revision",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/catalog-revisions/<uuid:catalog_revision_id>/",
        CatalogRevisionDetailAPIEndpoint.as_view(http_method_names=["get"]),
        name="catalog-revision",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/catalog-revisions/<uuid:catalog_revision_id>/approve/",
        CatalogRevisionApproveAPIEndpoint.as_view(http_method_names=["post"]),
        name="catalog-revision-approve",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/catalog-revisions/<uuid:catalog_revision_id>/reject/",
        CatalogRevisionRejectAPIEndpoint.as_view(http_method_names=["post"]),
        name="catalog-revision-reject",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/catalog-revisions/<uuid:catalog_revision_id>/rollback/",
        CatalogRevisionRollbackAPIEndpoint.as_view(http_method_names=["post"]),
        name="catalog-revision-rollback",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/compatibility-checks/",
        CompatibilityCheckAPIEndpoint.as_view(http_method_names=["get"]),
        name="compatibility-check",
    ),
]
