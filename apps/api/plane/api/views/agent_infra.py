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
            from django.db import transaction
            from plane.agent_infra.services.assignment_queue import validate_knowledge_context

            with transaction.atomic():
                assignment = serializer.save(workspace_id=project.workspace_id, project_id=project_id)
                try:
                    validate_knowledge_context(assignment)
                except DjangoValidationError as exc:
                    transaction.set_rollback(True)
                    messages = exc.message_dict.get("knowledge_context", exc.messages)
                    message = messages[0] if isinstance(messages, list) else str(messages)
                    return agent_infra_error_response(
                        "KNOWLEDGE_CONTEXT_INVALID",
                        message,
                        status.HTTP_409_CONFLICT,
                        correlation_id=request.headers.get("X-Request-Id"),
                    )
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
                knowledge_messages = exc.message_dict.get("knowledge_context", None)
                if knowledge_messages:
                    message = knowledge_messages[0] if isinstance(knowledge_messages, list) else str(knowledge_messages)
                    return agent_infra_error_response(
                        "KNOWLEDGE_CONTEXT_INVALID",
                        message,
                        status.HTTP_409_CONFLICT,
                        correlation_id=request.headers.get("X-Request-Id"),
                    )
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

        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        approved_versions = KnowledgeVersion.objects.filter(
            source=source,
            status=VersionStatus.APPROVED,
        )
        for version in approved_versions:
            KnowledgeIndexRecord.objects.get_or_create(
                workspace_id=project.workspace_id,
                project_id=project_id,
                knowledge_version=version,
                action=IndexAction.DELETE,
                status=IndexRequestStatus.PENDING,
                defaults={"created_by": request.user},
            )

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


@requires_service_identity("resolve_context")
class KnowledgeContextResolveAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Resolve context candidates by enforcing authority over similarity.

    Accepts a list of candidate knowledge version IDs with optional similarity
    scores. Returns the candidates ranked/filtered by authority policy:
    - Only approved versions are eligible
    - Higher authority ranks override higher similarity scores
    - Authority type and provenance labels are carried on each result
    """

    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id):
        from plane.agent_infra.services.knowledge_authority import (
            get_knowledge_authority_service,
            AUTHORITY_RANK,
        )

        candidates = request.data.get("candidates", [])
        if not candidates:
            return agent_infra_validation_error_response(
                {"candidates": "At least one candidate is required"},
                request,
            )

        if not isinstance(candidates, list):
            return agent_infra_validation_error_response(
                {"candidates": "Must be a list of candidate objects"},
                request,
            )

        validated_candidates = []
        errors = []
        for idx, c in enumerate(candidates):
            if not isinstance(c, dict):
                errors.append(f"candidates[{idx}]: must be an object")
                continue
            version_id = c.get("version_id")
            if not version_id:
                errors.append(f"candidates[{idx}]: version_id is required")
                continue
            try:
                import uuid
                uuid.UUID(str(version_id))
            except (ValueError, AttributeError):
                errors.append(f"candidates[{idx}]: version_id must be a valid UUID")
                continue
            score = c.get("similarity_score", 0.0)
            try:
                score = float(score)
            except (TypeError, ValueError):
                errors.append(
                    f"candidates[{idx}]: similarity_score must be numeric"
                )
                continue
            import math
            if not math.isfinite(score):
                errors.append(
                    f"candidates[{idx}]: similarity_score must be a finite number"
                )
                continue
            validated_candidates.append(
                {"version_id": str(version_id), "similarity_score": score}
            )

        if errors:
            return agent_infra_validation_error_response(
                {"candidates": errors},
                request,
            )

        version_ids = [c["version_id"] for c in validated_candidates]
        similarity_map = {
            c["version_id"]: c["similarity_score"]
            for c in validated_candidates
        }

        versions = list(
            KnowledgeVersion.objects.filter(
                pk__in=version_ids,
                workspace__slug=slug,
                project_id=project_id,
            ).select_related("source")
        )

        authority_service = get_knowledge_authority_service()
        resolved = []

        for version in versions:
            is_authoritative = authority_service.enforce_authority_level(
                version, vector_similarity_score=similarity_map.get(str(version.id), 0.0)
            )
            authority_type = version.source.authority_type
            resolved.append(
                {
                    "version_id": str(version.id),
                    "source_id": str(version.source_id),
                    "source_name": version.source.name,
                    "authority_type": authority_type,
                    "authority_rank": AUTHORITY_RANK.get(authority_type, 0),
                    "is_authoritative": is_authoritative,
                    "status": version.status,
                    "version_number": version.version_number,
                    "is_agent_generated": version.is_agent_generated,
                    "similarity_score": similarity_map.get(str(version.id), 0.0),
                    "provenance": "agent" if version.is_agent_generated else "human",
                    "eligible": version.status == VersionStatus.APPROVED,
                }
            )

        resolved.sort(
            key=lambda r: (-r["authority_rank"], -r["similarity_score"])
        )

        eligible = [r for r in resolved if r["eligible"]]
        ineligible = [r for r in resolved if not r["eligible"]]

        return Response(
            {
                "resolved": eligible,
                "ineligible": ineligible,
                "policy_applied": "authority_overrides_similarity",
            },
            status=status.HTTP_200_OK,
        )


class KnowledgeIndexRecordListCreateAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Manage knowledge index reconciliation requests.

    POST creates reindex/deletion requests for knowledge versions.
    GET returns the index reconciliation state for the project.
    """

    serializer_class = KnowledgeIndexRecordSerializer
    model = KnowledgeIndexRecord
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            KnowledgeIndexRecord.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .filter(project__archived_at__isnull=True)
            .select_related("knowledge_version", "knowledge_version__source")
            .distinct()
        )

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
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
                {"knowledge_version": "knowledge_version is required"},
                request,
            )
        if action not in [IndexAction.REINDEX, IndexAction.DELETE]:
            return agent_infra_validation_error_response(
                {"action": "action must be 'reindex' or 'delete'"},
                request,
            )

        try:
            version = KnowledgeVersion.objects.get(
                pk=version_id,
                workspace__slug=slug,
                project_id=project_id,
            )
        except KnowledgeVersion.DoesNotExist:
            return agent_infra_validation_error_response(
                {"knowledge_version": "Knowledge version not found in this project"},
                request,
            )

        record = KnowledgeIndexRecord.objects.create(
            workspace_id=project.workspace_id,
            project_id=project_id,
            knowledge_version=version,
            action=action,
            status=IndexRequestStatus.PENDING,
            created_by=request.user,
        )
        return Response(
            KnowledgeIndexRecordSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )


@requires_service_identity("update_index_records", methods=["PATCH"])
class KnowledgeIndexRecordDetailAPIEndpoint(AgentInfraFeatureFlagMixin, BaseAPIView):
    """Acknowledge or update index reconciliation state (service identity)."""

    serializer_class = KnowledgeIndexRecordSerializer
    model = KnowledgeIndexRecord
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return KnowledgeIndexRecord.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
        )

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs.get("record_id"))

    def get(self, request, slug, project_id, record_id):
        record = self.get_object()
        return Response(
            KnowledgeIndexRecordSerializer(record).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, record_id):
        """Update index record status (acknowledge, complete, fail).

        Used by Development Center service to report back index state.
        """
        from django.db import transaction

        new_status = request.data.get("status")
        now = timezone.now()

        valid_transitions = {
            IndexRequestStatus.PENDING: {
                IndexRequestStatus.ACKNOWLEDGED,
                IndexRequestStatus.FAILED,
            },
            IndexRequestStatus.ACKNOWLEDGED: {
                IndexRequestStatus.IN_PROGRESS,
                IndexRequestStatus.FAILED,
            },
            IndexRequestStatus.IN_PROGRESS: {
                IndexRequestStatus.COMPLETED,
                IndexRequestStatus.FAILED,
            },
            IndexRequestStatus.FAILED: {
                IndexRequestStatus.PENDING,
            },
        }

        with transaction.atomic():
            record = (
                KnowledgeIndexRecord.objects.select_for_update()
                .get(pk=record_id, workspace__slug=slug, project_id=project_id)
            )

            allowed = valid_transitions.get(record.status, set())
            if new_status and new_status not in allowed:
                return agent_infra_error_response(
                    INVALID_STATUS_TRANSITION,
                    f"Cannot transition index record from '{record.status}' to '{new_status}'",
                    status.HTTP_409_CONFLICT,
                    correlation_id=request.headers.get("X-Request-Id"),
                )

            if new_status == IndexRequestStatus.ACKNOWLEDGED:
                record.acknowledged_at = now
            elif new_status == IndexRequestStatus.COMPLETED:
                record.completed_at = now
                record.is_verified = True
                record.last_observed_at = now
            elif new_status == IndexRequestStatus.FAILED:
                record.failed_at = now
                record.failure_reason = request.data.get("failure_reason", "")
                record.retry_count += 1

            if new_status:
                record.status = new_status

            external_ref = request.data.get("external_ref")
            if external_ref:
                record.external_ref = external_ref

            record.save()

        return Response(
            KnowledgeIndexRecordSerializer(record).data,
            status=status.HTTP_200_OK,
        )


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
        serializer = KnowledgeConflictSerializer(
            data=request.data,
            context={"workspace_id": project.workspace_id, "project_id": project_id},
        )
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
                .get(pk=conflict_id, workspace__slug=slug, project_id=project_id)
            )
            new_status = request.data.get("status")

            if new_status == ConflictStatus.RESOLVED and not request.data.get("resolution_summary"):
                return agent_infra_validation_error_response(
                    {"resolution_summary": "Required when resolving a conflict"}, request
                )

            serializer = KnowledgeConflictSerializer(
                conflict, data=request.data, partial=True,
                context={"workspace_id": conflict.workspace_id, "project_id": project_id},
            )
            if serializer.is_valid():
                save_kwargs = {}
                if new_status == ConflictStatus.RESOLVED:
                    save_kwargs["resolved_by"] = request.user
                    save_kwargs["resolved_at"] = timezone.now()
                serializer.save(**save_kwargs)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return agent_infra_validation_error_response(serializer.errors, request)
