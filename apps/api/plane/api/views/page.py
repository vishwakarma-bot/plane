# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers import PageArchiveSerializer, PageSerializer
from plane.api.views.base import BaseAPIView
from plane.db.models import Page, Project, ProjectMember, ProjectPage
from plane.utils.permissions import ProjectEntityPermission
from plane.db.models.project import ROLE


class PageListCreateAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return (
            Page.objects.filter(
                workspace__slug=self.kwargs["slug"],
                project_pages__project_id=self.kwargs["project_id"],
                project_pages__deleted_at__isnull=True,
            )
            .filter(Q(access=Page.PUBLIC_ACCESS) | Q(owned_by=self.request.user))
            .select_related("workspace", "owned_by")
            .distinct()
        )

    def get(self, request, slug, project_id):
        pages = self.get_queryset().order_by("-created_at")
        return self.paginate(
            request=request,
            queryset=pages,
            on_results=lambda results: PageSerializer(results, many=True).data,
            default_per_page=20,
        )

    @transaction.atomic
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        serializer = PageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent = serializer.validated_data.get("parent")
        if (
            parent
            and not ProjectPage.objects.filter(
                page=parent,
                project=project,
                workspace=project.workspace,
                deleted_at__isnull=True,
            ).exists()
        ):
            return Response(
                {"parent": ["Parent page must belong to this project."]}, status=status.HTTP_400_BAD_REQUEST
            )

        page = serializer.save(
            workspace=project.workspace,
            owned_by=request.user,
        )
        ProjectPage.objects.create(
            workspace=project.workspace,
            project=project,
            page=page,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(PageSerializer(page).data, status=status.HTTP_201_CREATED)


class PageDetailAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_page(self, slug, project_id, page_id):
        return Page.objects.select_related("workspace", "owned_by").get(
            pk=page_id,
            workspace__slug=slug,
            project_pages__project_id=project_id,
            project_pages__deleted_at__isnull=True,
        )

    def get(self, request, slug, project_id, page_id):
        page = self.get_page(slug, project_id, page_id)
        if page.access == Page.PRIVATE_ACCESS and page.owned_by_id != request.user.id:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PageSerializer(page).data)

    def patch(self, request, slug, project_id, page_id):
        page = self.get_page(slug, project_id, page_id)
        if page.is_locked:
            return Response({"error": "Page is locked"}, status=status.HTTP_400_BAD_REQUEST)
        if "access" in request.data and page.owned_by_id != request.user.id:
            return Response({"error": "Only the page owner can update access"}, status=status.HTTP_403_FORBIDDEN)

        serializer = PageSerializer(page, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get("parent")
        if (
            parent
            and not ProjectPage.objects.filter(
                page=parent,
                project_id=project_id,
                workspace__slug=slug,
                deleted_at__isnull=True,
            ).exists()
        ):
            return Response(
                {"parent": ["Parent page must belong to this project."]}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, slug, project_id, page_id):
        page = self.get_page(slug, project_id, page_id)
        if page.archived_at is None:
            return Response({"error": "The page must be archived before deletion"}, status=status.HTTP_400_BAD_REQUEST)
        is_admin = ProjectMember.objects.filter(
            project_id=project_id,
            workspace__slug=slug,
            member=request.user,
            role=ROLE.ADMIN.value,
            is_active=True,
        ).exists()
        if page.owned_by_id != request.user.id and not is_admin:
            return Response(
                {"error": "Only an admin or the page owner can delete the page"}, status=status.HTTP_403_FORBIDDEN
            )
        Page.objects.filter(parent=page, workspace__slug=slug).update(parent=None)
        page.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PageArchiveAPIEndpoint(PageDetailAPIEndpoint):
    def patch(self, request, slug, project_id, page_id):
        serializer = PageArchiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = self.get_page(slug, project_id, page_id)
        if page.owned_by_id != request.user.id:
            is_admin = ProjectMember.objects.filter(
                project_id=project_id,
                workspace__slug=slug,
                member=request.user,
                role=ROLE.ADMIN.value,
                is_active=True,
            ).exists()
            if not is_admin:
                return Response(
                    {"error": "Only an admin or the page owner can archive the page"}, status=status.HTTP_403_FORBIDDEN
                )

        page.archived_at = timezone.now().date() if serializer.validated_data["archived"] else None
        page.save(update_fields=["archived_at", "updated_at"])
        return Response(PageSerializer(page).data)
