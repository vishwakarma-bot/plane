# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.agent_infra.decorators import idempotent_callback
from plane.agent_infra.auth import requires_service_identity
from plane.agent_infra.error_format import (
    INVALID_STATUS_TRANSITION,
    REVIEW_REQUIRED,
    agent_infra_error_response,
    agent_infra_validation_error_response,
)
from plane.agent_infra.mixins import AgentInfraFeatureFlagMixin
from plane.agent_infra.services import get_catalog_service
from plane.agent_infra.services.assignment_queue import claim_assignment
from plane.agent_infra.services.reconciliation import get_reconciliation_service
from plane.agent_infra.models import (
    AgentAssignment,
    AgentInfraAttentionItem,
    AgentRun,
    ArtifactReference,
    AssignmentStatus,
    AuthorizingReview,
    ContextManifest,
    KnowledgeSource,
    KnowledgeVersion,
    ReviewDisposition,
    VersionStatus,
)
from plane.api.serializers import (
    AgentAssignmentSerializer,
    AgentCatalogSectionSerializer,
    AgentCatalogSerializer,
    AgentInfraAttentionItemSerializer,
    AgentRunSerializer,
    AgentSyncStatusSerializer,
    ArtifactReferenceSerializer,
    AuthorizingReviewSerializer,
    ContextManifestSerializer,
    KnowledgeSourceSerializer,
    KnowledgeVersionSerializer,
    ReviewDispositionSerializer,
)
from plane.app.permissions import ProjectEntityPermission
from plane.db.models import Issue, Project
from plane.api.views.base import BaseAPIView


class AgentAssignmentListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AgentAssignmentSerializer
    model = AgentAssignment
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        queryset = (
            AgentAssignment.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project", "work_item")
            .distinct()
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda assignments: AgentAssignmentSerializer(
                assignments, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    @idempotent_callback
    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        work_item_id = request.data.get("work_item")
        if work_item_id and not Issue.objects.filter(
            pk=work_item_id,
            workspace__slug=slug,
            project_id=project_id,
        ).exists():
            return agent_infra_validation_error_response(
                {"work_item": "Work item not found in this project"},
                request,
            )

        serializer = AgentAssignmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace_id=project.workspace_id, project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class AgentAssignmentDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AgentAssignmentSerializer
    model = AgentAssignment
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            AgentAssignment.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project", "work_item")
            .distinct()
        )

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs.get("assignment_id"))

    def get(self, request, slug, project_id, assignment_id):
        assignment = self.get_object()
        return Response(
            AgentAssignmentSerializer(assignment, fields=self.fields, expand=self.expand).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, assignment_id):
        assignment = self.get_object()
        new_status = request.data.get("status")

        if new_status == AssignmentStatus.RUNNING and assignment.status != AssignmentStatus.RUNNING:
            identity = getattr(request, "service_identity", None)
            if not identity:
                return agent_infra_error_response(
                    "SERVICE_IDENTITY_REQUIRED",
                    "A valid service identity is required to claim assignments.",
                    status.HTTP_401_UNAUTHORIZED,
                    correlation_id=request.headers.get("X-Request-Id"),
                )
            if identity.workspace.slug != slug:
                return agent_infra_error_response(
                    "PERMISSION_DENIED",
                    "Service identity is not authorized for this workspace.",
                    status.HTTP_403_FORBIDDEN,
                    correlation_id=request.headers.get("X-Request-Id"),
                )
            permissions = identity.permissions or []
            if "claim_assignments" not in permissions:
                return agent_infra_error_response(
                    "PERMISSION_DENIED",
                    "Service identity lacks required permission: claim_assignments",
                    status.HTTP_403_FORBIDDEN,
                    correlation_id=request.headers.get("X-Request-Id"),
                )

            service_actor = identity.service_id
            try:
                assignment = claim_assignment(assignment.pk, service_actor)
            except DjangoValidationError as exc:
                messages = exc.message_dict.get("status", exc.messages)
                message = messages[0] if isinstance(messages, list) else str(messages)
                correlation_id = request.headers.get("X-Request-Id")
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    message,
                    status.HTTP_409_CONFLICT,
                    correlation_id=correlation_id,
                )

        serializer = AgentAssignmentSerializer(assignment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return agent_infra_validation_error_response(serializer.errors, request)

    def delete(self, request, slug, project_id, assignment_id):
        assignment = self.get_object()
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@requires_service_identity("report_runs")
class AgentRunListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AgentRunSerializer
    model = AgentRun
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            AgentRun.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project", "assignment")
            .distinct()
        )

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda runs: AgentRunSerializer(runs, many=True, fields=self.fields, expand=self.expand).data,
        )

    @idempotent_callback
    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        assignment_id = request.data.get("assignment")

        if not assignment_id:
            return agent_infra_validation_error_response(
                {"assignment": "assignment is required"},
                request,
            )

        if not AgentAssignment.objects.filter(
            pk=assignment_id,
            workspace__slug=slug,
            project_id=project_id,
        ).exists():
            return agent_infra_validation_error_response(
                {"assignment": "Assignment not found in this project"},
                request,
            )

        assignment = AgentAssignment.objects.get(
            pk=assignment_id,
            workspace__slug=slug,
            project_id=project_id,
        )

        serializer = AgentRunSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                workspace_id=project.workspace_id,
                project_id=project_id,
                assignment=assignment,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class AgentRunDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AgentRunSerializer
    model = AgentRun
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            AgentRun.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project", "assignment")
            .distinct()
        )

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs.get("run_id"))

    def get(self, request, slug, project_id, run_id):
        agent_run = self.get_object()
        return Response(
            AgentRunSerializer(agent_run, fields=self.fields, expand=self.expand).data,
            status=status.HTTP_200_OK,
        )


@requires_service_identity("report_reviews")
class AuthorizingReviewListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AuthorizingReviewSerializer
    model = AuthorizingReview
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_agent_run(self):
        return AgentRun.objects.get(
            pk=self.kwargs.get("run_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        )

    def get_queryset(self):
        return AuthorizingReview.objects.filter(
            run_id=self.kwargs.get("run_id"),
            run__workspace__slug=self.kwargs.get("slug"),
            run__project_id=self.kwargs.get("project_id"),
        ).select_related("run")

    def get(self, request, slug, project_id, run_id):
        self.get_agent_run()
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda reviews: AuthorizingReviewSerializer(
                reviews, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    @idempotent_callback
    def post(self, request, slug, project_id, run_id):
        agent_run = self.get_agent_run()
        serializer = AuthorizingReviewSerializer(
            data=request.data,
            context={"run": agent_run},
        )
        if serializer.is_valid():
            serializer.save(run=agent_run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


@requires_service_identity("report_artifacts")
class ArtifactReferenceListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = ArtifactReferenceSerializer
    model = ArtifactReference
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_agent_run(self):
        return AgentRun.objects.get(
            pk=self.kwargs.get("run_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        )

    def get_queryset(self):
        return ArtifactReference.objects.filter(
            run_id=self.kwargs.get("run_id"),
            run__workspace__slug=self.kwargs.get("slug"),
            run__project_id=self.kwargs.get("project_id"),
        ).select_related("run")

    def get(self, request, slug, project_id, run_id):
        self.get_agent_run()
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda artifacts: ArtifactReferenceSerializer(
                artifacts, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    @idempotent_callback
    def post(self, request, slug, project_id, run_id):
        agent_run = self.get_agent_run()
        serializer = ArtifactReferenceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(run=agent_run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class AgentCatalogAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """
    Read-only catalog of agent and skill definitions.
    GET /api/v1/workspaces/{slug}/projects/{project_id}/agent-catalog/
    """

    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get(self, request, slug, project_id):
        catalog_path = os.environ.get("AGENT_CATALOG_PATH")
        if not catalog_path:
            return Response(
                {
                    "status": "unavailable",
                    "message": "Agent catalog path not configured",
                },
                status=status.HTTP_200_OK,
            )

        service = get_catalog_service()
        catalog = service.get_catalog()
        return Response(AgentCatalogSerializer(catalog).data, status=status.HTTP_200_OK)


class AgentCatalogSectionAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Read-only catalog section endpoint for a single catalog type."""

    permission_classes = [ProjectEntityPermission]
    use_read_replica = True
    catalog_method = ""
    unavailable_message = "Agent catalog path not configured"

    def get(self, request, slug, project_id):
        catalog_path = os.environ.get("AGENT_CATALOG_PATH")
        if not catalog_path:
            return Response(
                {
                    "status": "unavailable",
                    "message": self.unavailable_message,
                },
                status=status.HTTP_200_OK,
            )

        service = get_catalog_service()
        getter = getattr(service, self.catalog_method)
        items = getter()
        has_errors = any(entry.get("status") == "error" for entry in items)
        payload = {
            "status": "stale" if has_errors else "available",
            "last_refreshed": service.last_refreshed,
            "items": items,
        }
        return Response(AgentCatalogSectionSerializer(payload).data, status=status.HTTP_200_OK)


class AgentCatalogWorkforceAPIEndpoint(AgentCatalogSectionAPIEndpoint):
    catalog_method = "get_agents"


class AgentCatalogSkillsAPIEndpoint(AgentCatalogSectionAPIEndpoint):
    catalog_method = "get_skills"


class AgentCatalogModelsAPIEndpoint(AgentCatalogSectionAPIEndpoint):
    catalog_method = "get_models"


class AgentCatalogEnvironmentsAPIEndpoint(AgentCatalogSectionAPIEndpoint):
    catalog_method = "get_environments"


class AgentCatalogIntegrationsAPIEndpoint(AgentCatalogSectionAPIEndpoint):
    catalog_method = "get_integrations"


class ReviewDispositionListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = ReviewDispositionSerializer
    model = ReviewDisposition
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_agent_run(self):
        return AgentRun.objects.get(
            pk=self.kwargs.get("run_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        )

    def get_queryset(self):
        return ReviewDisposition.objects.filter(
            run_id=self.kwargs.get("run_id"),
            run__workspace__slug=self.kwargs.get("slug"),
            run__project_id=self.kwargs.get("project_id"),
        ).select_related("run", "reviewer")

    def get(self, request, slug, project_id, run_id):
        self.get_agent_run()
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda dispositions: ReviewDispositionSerializer(
                dispositions, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    @idempotent_callback
    def post(self, request, slug, project_id, run_id):
        agent_run = self.get_agent_run()
        if not hasattr(agent_run, "authorizing_review"):
            correlation_id = request.headers.get("X-Request-Id")
            return agent_infra_error_response(
                REVIEW_REQUIRED,
                "An authorizing review must exist before creating a review disposition.",
                status.HTTP_400_BAD_REQUEST,
                correlation_id=correlation_id,
            )

        serializer = ReviewDispositionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(run=agent_run, reviewer=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class AgentInfraAttentionItemListAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AgentInfraAttentionItemSerializer
    model = AgentInfraAttentionItem
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        queryset = (
            AgentInfraAttentionItem.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                resolved_at__isnull=True,
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project")
            .distinct()
            .order_by("-created_at")
        )

        drift_type = self.request.query_params.get("drift_type")
        if drift_type:
            queryset = queryset.filter(drift_type=drift_type)

        return queryset

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda items: AgentInfraAttentionItemSerializer(
                items, many=True, fields=self.fields, expand=self.expand
            ).data,
        )


class AgentInfraAttentionItemDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = AgentInfraAttentionItemSerializer
    model = AgentInfraAttentionItem
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            AgentInfraAttentionItem.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project")
            .distinct()
        )

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs.get("attention_item_id"))

    def patch(self, request, slug, project_id, attention_item_id):
        attention_item = self.get_object()
        if attention_item.resolved_at is not None:
            return Response(
                {"error": "Attention item is already resolved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attention_item.resolved_at = timezone.now()
        attention_item.save(update_fields=["resolved_at", "updated_at"])
        return Response(
            AgentInfraAttentionItemSerializer(
                attention_item, fields=self.fields, expand=self.expand
            ).data,
            status=status.HTTP_200_OK,
        )


class AgentSyncStatusAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        sync_status = get_reconciliation_service().get_sync_status(
            workspace_id=project.workspace_id,
            project_id=project.id,
        )
        return Response(AgentSyncStatusSerializer(sync_status).data, status=status.HTTP_200_OK)


class KnowledgeSourceListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = KnowledgeSourceSerializer
    model = KnowledgeSource
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            KnowledgeSource.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project", "owner")
            .distinct()
        )

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda sources: KnowledgeSourceSerializer(
                sources, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        serializer = KnowledgeSourceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace_id=project.workspace_id, project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class KnowledgeSourceDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = KnowledgeSourceSerializer
    model = KnowledgeSource
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            KnowledgeSource.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("workspace", "project", "owner")
            .distinct()
        )

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs.get("source_id"))

    def get(self, request, slug, project_id, source_id):
        source = self.get_object()
        return Response(
            KnowledgeSourceSerializer(source, fields=self.fields, expand=self.expand).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, source_id):
        source = self.get_object()
        if source.is_retired:
            return agent_infra_validation_error_response(
                {"source": "Knowledge source is retired and cannot be updated."},
                request,
            )

        serializer = KnowledgeSourceSerializer(source, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return agent_infra_validation_error_response(serializer.errors, request)

    def delete(self, request, slug, project_id, source_id):
        source = self.get_object()
        if source.is_retired:
            return Response(status=status.HTTP_204_NO_CONTENT)

        source.is_retired = True
        source.retired_at = timezone.now()
        source.save(update_fields=["is_retired", "retired_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class KnowledgeVersionListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = KnowledgeVersionSerializer
    model = KnowledgeVersion
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_knowledge_source(self):
        return KnowledgeSource.objects.get(
            pk=self.kwargs.get("source_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
            is_retired=False,
        )

    def get_queryset(self):
        return (
            KnowledgeVersion.objects.filter(
                source_id=self.kwargs.get("source_id"),
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("source", "workspace", "project", "promoted_by")
            .distinct()
        )

    def get(self, request, slug, project_id, source_id):
        self.get_knowledge_source()
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda versions: KnowledgeVersionSerializer(
                versions, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id, source_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        source = self.get_knowledge_source()

        payload = dict(request.data)
        is_agent_generated = payload.get("is_agent_generated", False)
        if is_agent_generated:
            identity = getattr(request, "service_identity", None)
            if identity is None:
                return agent_infra_error_response(
                    "SERVICE_IDENTITY_REQUIRED",
                    "A valid service identity is required to report agent-generated knowledge.",
                    status.HTTP_401_UNAUTHORIZED,
                    correlation_id=request.headers.get("X-Request-Id"),
                )
            if identity.workspace.slug != slug:
                return agent_infra_error_response(
                    "PERMISSION_DENIED",
                    "Service identity is not authorized for this workspace.",
                    status.HTTP_403_FORBIDDEN,
                    correlation_id=request.headers.get("X-Request-Id"),
                )
            permissions = identity.permissions or []
            if "report_knowledge" not in permissions:
                return agent_infra_error_response(
                    "PERMISSION_DENIED",
                    "Service identity lacks required permission: report_knowledge",
                    status.HTTP_403_FORBIDDEN,
                    correlation_id=request.headers.get("X-Request-Id"),
                )
            payload["status"] = VersionStatus.QUARANTINED

        next_version_number = KnowledgeVersion.allocate_next_version_number(source)

        serializer = KnowledgeVersionSerializer(data=payload)
        if serializer.is_valid():
            serializer.save(
                source=source,
                workspace_id=project.workspace_id,
                project_id=project_id,
                version_number=next_version_number,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class KnowledgeVersionDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = KnowledgeVersionSerializer
    model = KnowledgeVersion
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            KnowledgeVersion.objects.filter(
                source_id=self.kwargs.get("source_id"),
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("source", "workspace", "project", "promoted_by")
            .distinct()
        )

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs.get("version_id"))

    def get(self, request, slug, project_id, source_id, version_id):
        version = self.get_object()
        return Response(
            KnowledgeVersionSerializer(version, fields=self.fields, expand=self.expand).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, source_id, version_id):
        version = self.get_object()
        new_status = request.data.get("status")

        if new_status and new_status != version.status:
            try:
                from plane.agent_infra.models import validate_version_status_transition

                validate_version_status_transition(
                    version.status,
                    new_status,
                    is_agent_generated=version.is_agent_generated,
                )
            except DjangoValidationError as exc:
                messages = exc.message_dict.get("status", exc.messages)
                message = messages[0] if isinstance(messages, list) else str(messages)
                correlation_id = request.headers.get("X-Request-Id")
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    message,
                    status.HTTP_409_CONFLICT,
                    correlation_id=correlation_id,
                )

        serializer = KnowledgeVersionSerializer(version, data=request.data, partial=True)
        if serializer.is_valid():
            save_kwargs = {}
            if new_status == VersionStatus.APPROVED and version.status != VersionStatus.APPROVED:
                save_kwargs["promoted_by"] = request.user
                save_kwargs["promoted_at"] = timezone.now()
            serializer.save(**save_kwargs)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return agent_infra_validation_error_response(serializer.errors, request)


@requires_service_identity("report_manifests")
class ContextManifestListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    serializer_class = ContextManifestSerializer
    model = ContextManifest
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_agent_run(self):
        return AgentRun.objects.get(
            pk=self.kwargs.get("run_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        )

    def get_queryset(self):
        return ContextManifest.objects.filter(
            run_id=self.kwargs.get("run_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        ).select_related("run", "knowledge_version", "workspace", "project")

    def get(self, request, slug, project_id, run_id):
        self.get_agent_run()
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda manifests: ContextManifestSerializer(
                manifests, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    @idempotent_callback
    def post(self, request, slug, project_id, run_id):
        agent_run = self.get_agent_run()
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        knowledge_version_id = request.data.get("knowledge_version")

        if not knowledge_version_id:
            return agent_infra_validation_error_response(
                {"knowledge_version": "knowledge_version is required"},
                request,
            )

        try:
            knowledge_version = KnowledgeVersion.objects.get(
                pk=knowledge_version_id,
                workspace__slug=slug,
                project_id=project_id,
            )
        except KnowledgeVersion.DoesNotExist:
            return agent_infra_validation_error_response(
                {"knowledge_version": "Knowledge version not found in this project"},
                request,
            )

        if knowledge_version.source.project_id != project_id:
            return agent_infra_validation_error_response(
                {"knowledge_version": "Knowledge version does not belong to this project"},
                request,
            )

        serializer = ContextManifestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                run=agent_run,
                knowledge_version=knowledge_version,
                workspace_id=project.workspace_id,
                project_id=project_id,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)
