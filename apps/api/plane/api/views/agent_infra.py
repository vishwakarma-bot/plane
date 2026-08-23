# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.agent_infra.models import (
    AgentAssignment,
    AgentRun,
    ArtifactReference,
    AuthorizingReview,
    ReviewDisposition,
)
from plane.api.serializers import (
    AgentAssignmentSerializer,
    AgentRunSerializer,
    ArtifactReferenceSerializer,
    AuthorizingReviewSerializer,
    ReviewDispositionSerializer,
)
from plane.app.permissions import ProjectEntityPermission
from plane.db.models import Project
from plane.api.views.base import BaseAPIView


class AgentAssignmentListCreateAPIEndpoint(BaseAPIView):
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

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda assignments: AgentAssignmentSerializer(
                assignments, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        serializer = AgentAssignmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace_id=project.workspace_id, project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentAssignmentDetailAPIEndpoint(BaseAPIView):
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
        serializer = AgentAssignmentSerializer(assignment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug, project_id, assignment_id):
        assignment = self.get_object()
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentRunListCreateAPIEndpoint(BaseAPIView):
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

    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        assignment_id = request.data.get("assignment")

        if not assignment_id:
            return Response({"error": "assignment is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not AgentAssignment.objects.filter(
            pk=assignment_id,
            workspace__slug=slug,
            project_id=project_id,
        ).exists():
            return Response({"error": "Assignment not found in this project"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AgentRunSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace_id=project.workspace_id, project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentRunDetailAPIEndpoint(BaseAPIView):
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

    def patch(self, request, slug, project_id, run_id):
        agent_run = self.get_object()
        serializer = AgentRunSerializer(agent_run, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug, project_id, run_id):
        agent_run = self.get_object()
        agent_run.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthorizingReviewListCreateAPIEndpoint(BaseAPIView):
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

    def post(self, request, slug, project_id, run_id):
        agent_run = self.get_agent_run()
        serializer = AuthorizingReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(run=agent_run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ArtifactReferenceListCreateAPIEndpoint(BaseAPIView):
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

    def post(self, request, slug, project_id, run_id):
        agent_run = self.get_agent_run()
        serializer = ArtifactReferenceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(run=agent_run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReviewDispositionListCreateAPIEndpoint(BaseAPIView):
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

    def post(self, request, slug, project_id, run_id):
        agent_run = self.get_agent_run()
        serializer = ReviewDispositionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(run=agent_run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
