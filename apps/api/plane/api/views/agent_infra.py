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
    IndexAction,
    IndexRequestStatus,
    KnowledgeConflict,
    KnowledgeIndexRecord,
    KnowledgeSource,
    KnowledgeVersion,
    ReviewDisposition,
    VersionStatus,
)
from plane.api.serializers import (
    AgentAssignmentSerializer,
    AgentCatalogSerializer,
    AgentInfraAttentionItemSerializer,
    AgentRunSerializer,
    AgentSyncStatusSerializer,
    ArtifactReferenceSerializer,
    AuthorizingReviewSerializer,
    ContextManifestSerializer,
    KnowledgeConflictSerializer,
    KnowledgeIndexRecordSerializer,
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

        latest_version = (
            KnowledgeVersion.objects.filter(source=source)
            .order_by("-version_number")
            .values_list("version_number", flat=True)
            .first()
        )
        next_version_number = (latest_version or 0) + 1

        serializer = KnowledgeVersionSerializer(data=payload)
        if serializer.is_valid():
            from django.db import IntegrityError

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    serializer.save(
                        source=source,
                        workspace_id=project.workspace_id,
                        project_id=project_id,
                        version_number=next_version_number,
                    )
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                except IntegrityError:
                    if attempt == max_retries - 1:
                        return agent_infra_error_response(
                            INVALID_STATUS_TRANSITION,
                            "Concurrent version creation conflict. Please retry.",
                            status.HTTP_409_CONFLICT,
                            correlation_id=request.headers.get("X-Request-Id"),
                        )
                    next_version_number = KnowledgeVersion.allocate_next_version_number(source)
                    serializer = KnowledgeVersionSerializer(data=payload)
                    serializer.is_valid()
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
        from django.db import transaction

        with transaction.atomic():
            version = (
                KnowledgeVersion.objects.select_for_update()
                .get(pk=version_id, source_id=source_id, project_id=project_id)
            )
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

                if new_status == VersionStatus.APPROVED:
                    from plane.agent_infra.services.knowledge_authority import (
                        get_knowledge_authority_service,
                    )

                    authority_service = get_knowledge_authority_service()
                    is_valid, reason = authority_service.validate_promotion(
                        version,
                        promoter_user=request.user,
                        target_status=VersionStatus.APPROVED,
                    )
                    if not is_valid:
                        return agent_infra_error_response(
                            "AUTHORITY_REVIEWER_REQUIRED",
                            reason,
                            status.HTTP_403_FORBIDDEN,
                            correlation_id=request.headers.get("X-Request-Id"),
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


@requires_service_identity("resolve_context")
class KnowledgeContextResolveAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Resolve knowledge context for a project, prioritizing authority over similarity."""

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)

        from plane.agent_infra.services.knowledge_authority import (
            get_knowledge_authority_service,
        )

        service = get_knowledge_authority_service()
        context = service.resolve_context(
            project=project,
            query=request.data.get("query", ""),
            max_results=request.data.get("max_results", 10),
        )
        return Response(context, status=status.HTTP_200_OK)


class KnowledgeIndexRecordListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """List and create index reconciliation records."""

    serializer_class = KnowledgeIndexRecordSerializer
    model = KnowledgeIndexRecord
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return KnowledgeIndexRecord.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        ).select_related("knowledge_version", "workspace", "project")

    def get(self, request, slug, project_id):
        filter_status = request.query_params.get("status")
        qs = self.get_queryset()
        if filter_status:
            qs = qs.filter(status=filter_status)
        return self.paginate(
            request=request,
            queryset=qs,
            on_results=lambda records: KnowledgeIndexRecordSerializer(
                records, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        version_id = request.data.get("knowledge_version")
        action = request.data.get("action")

        if not version_id:
            return agent_infra_validation_error_response(
                {"knowledge_version": "knowledge_version is required"}, request
            )
        if action not in [c[0] for c in IndexAction.choices]:
            return agent_infra_validation_error_response(
                {"action": f"Must be one of: {[c[0] for c in IndexAction.choices]}"}, request
            )

        try:
            version = KnowledgeVersion.objects.get(
                pk=version_id, project_id=project_id
            )
        except KnowledgeVersion.DoesNotExist:
            return agent_infra_validation_error_response(
                {"knowledge_version": "Version not found in this project"}, request
            )

        serializer = KnowledgeIndexRecordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                knowledge_version=version,
                workspace_id=project.workspace_id,
                project_id=project_id,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class KnowledgeIndexRecordDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Update index record status (acknowledge, complete, fail)."""

    serializer_class = KnowledgeIndexRecordSerializer
    model = KnowledgeIndexRecord
    permission_classes = [ProjectEntityPermission]

    def get_object(self):
        return KnowledgeIndexRecord.objects.get(
            pk=self.kwargs.get("record_id"),
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        )

    def get(self, request, slug, project_id, record_id):
        record = self.get_object()
        return Response(
            KnowledgeIndexRecordSerializer(record).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, record_id):
        from django.db import transaction

        with transaction.atomic():
            record = (
                KnowledgeIndexRecord.objects.select_for_update()
                .get(pk=record_id, project_id=project_id)
            )
            new_status = request.data.get("status")

            valid_transitions = {
                IndexRequestStatus.PENDING: {IndexRequestStatus.ACKNOWLEDGED},
                IndexRequestStatus.ACKNOWLEDGED: {IndexRequestStatus.IN_PROGRESS},
                IndexRequestStatus.IN_PROGRESS: {
                    IndexRequestStatus.COMPLETED,
                    IndexRequestStatus.FAILED,
                },
                IndexRequestStatus.FAILED: {IndexRequestStatus.PENDING},
            }

            allowed = valid_transitions.get(record.status, set())
            if new_status and new_status not in allowed:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    f"Cannot transition from '{record.status}' to '{new_status}'.",
                    status.HTTP_409_CONFLICT,
                    correlation_id=request.headers.get("X-Request-Id"),
                )

            if new_status == IndexRequestStatus.ACKNOWLEDGED:
                record.acknowledged_at = timezone.now()
            elif new_status == IndexRequestStatus.COMPLETED:
                record.completed_at = timezone.now()
                record.is_verified = True
            elif new_status == IndexRequestStatus.FAILED:
                record.failed_at = timezone.now()
                record.failure_reason = request.data.get("failure_reason", "")
                record.retry_count += 1

            serializer = KnowledgeIndexRecordSerializer(
                record, data=request.data, partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return agent_infra_validation_error_response(serializer.errors, request)


class KnowledgeConflictListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """List and create knowledge conflicts."""

    serializer_class = KnowledgeConflictSerializer
    model = KnowledgeConflict
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return (
            KnowledgeConflict.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related(
                "version_a", "version_b", "resolved_by", "winning_version"
            )
            .distinct()
        )

    def get(self, request, slug, project_id):
        filter_status = request.query_params.get("status")
        qs = self.get_queryset()
        if filter_status:
            qs = qs.filter(status=filter_status)
        return self.paginate(
            request=request,
            queryset=qs,
            on_results=lambda conflicts: KnowledgeConflictSerializer(
                conflicts, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        serializer = KnowledgeConflictSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                workspace_id=project.workspace_id,
                project_id=project_id,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return agent_infra_validation_error_response(serializer.errors, request)


class KnowledgeConflictDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Retrieve and resolve knowledge conflicts."""

    serializer_class = KnowledgeConflictSerializer
    model = KnowledgeConflict
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return (
            KnowledgeConflict.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related(
                "version_a", "version_b", "resolved_by", "winning_version"
            )
            .distinct()
        )

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs.get("conflict_id"))

    def get(self, request, slug, project_id, conflict_id):
        conflict = self.get_object()
        return Response(
            KnowledgeConflictSerializer(conflict).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, conflict_id):
        from django.db import transaction
        from plane.agent_infra.models import ConflictStatus

        with transaction.atomic():
            conflict = (
                KnowledgeConflict.objects.select_for_update()
                .get(pk=conflict_id, project_id=project_id)
            )
            new_status = request.data.get("status")

            if new_status == ConflictStatus.RESOLVED and not request.data.get("resolution_summary"):
                return agent_infra_validation_error_response(
                    {"resolution_summary": "Required when resolving a conflict"}, request
                )

            serializer = KnowledgeConflictSerializer(
                conflict, data=request.data, partial=True
            )
            if serializer.is_valid():
                save_kwargs = {}
                if new_status == ConflictStatus.RESOLVED:
                    save_kwargs["resolved_by"] = request.user
                    save_kwargs["resolved_at"] = timezone.now()
                serializer.save(**save_kwargs)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return agent_infra_validation_error_response(serializer.errors, request)
