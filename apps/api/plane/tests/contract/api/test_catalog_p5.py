# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import re

import pytest
from rest_framework import status

from plane.agent_infra.services import catalog as catalog_module
from plane.agent_infra.services.catalog import (
    ENVIRONMENT_PUBLIC_FIELDS,
    INTEGRATION_PUBLIC_FIELDS,
    MODEL_PUBLIC_FIELDS,
    AgentCatalogService,
)
from plane.db.models import Project, ProjectMember


SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@pytest.fixture
def catalog_root(tmp_path):
    root = tmp_path / "agent-catalog"
    for directory in ("agents", "skills", "models", "environments", "integrations"):
        (root / directory).mkdir(parents=True)
    (root / "skills" / "dev-engineer").mkdir(parents=True)
    return root


@pytest.fixture
def catalog_service(catalog_root, monkeypatch):
    monkeypatch.setenv("AGENT_CATALOG_PATH", str(catalog_root))
    catalog_module._catalog_service = None
    return AgentCatalogService(str(catalog_root))


@pytest.fixture
def agent_infra_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Agent Infra Project",
        identifier="AIP",
        workspace=workspace,
        created_by=create_user,
        is_agent_infra_enabled=True,
    )
    ProjectMember.objects.create(
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    return project


def write_agent(catalog_root, filename, content):
    (catalog_root / "agents" / filename).write_text(content, encoding="utf-8")


def write_skill(catalog_root, skill_name, frontmatter, body="Skill body paragraph."):
    skill_dir = catalog_root / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\n{frontmatter}\n---\n\n{body}"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return content


def write_model(catalog_root, filename, content):
    (catalog_root / "models" / filename).write_text(content, encoding="utf-8")


def write_environment(catalog_root, filename, content):
    (catalog_root / "environments" / filename).write_text(content, encoding="utf-8")


def write_integration(catalog_root, filename, content):
    (catalog_root / "integrations" / filename).write_text(content, encoding="utf-8")


def catalog_url(workspace_slug, project_id, section=None):
    base = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/agent-catalog/"
    return f"{base}{section}/" if section else base


def seed_catalog(catalog_root):
    write_agent(
        catalog_root,
        "dev-engineer.yaml",
        "\n".join(
            [
                "name: dev-engineer",
                "model_preference: gpt-4",
                "description: Development agent",
                "skills:",
                "  - skills/dev-engineer/SKILL.md",
                "tools:",
                "  - terminal",
            ]
        ),
    )
    write_skill(
        catalog_root,
        "dev-engineer",
        "name: dev-engineer\ndescription: Development skill\n",
    )
    write_model(
        catalog_root,
        "gpt-4.yaml",
        "\n".join(
            [
                "name: gpt-4",
                "provider: openai",
                "capabilities:",
                "  - code-generation",
                "credential_ref: openai-prod",
            ]
        ),
    )
    write_environment(
        catalog_root,
        "python-dev.yaml",
        "\n".join(
            [
                "name: python-dev",
                "description: Python environment",
                "toolchain:",
                "  - python-3.12",
                "credential_refs:",
                "  - pypi-readonly",
            ]
        ),
    )
    write_integration(
        catalog_root,
        "plane-mcp.yaml",
        "\n".join(
            [
                "name: plane-mcp",
                "type: mcp",
                "description: Plane MCP integration",
                "credential_ref: plane-mcp-token",
            ]
        ),
    )


@pytest.mark.contract
class TestAgentCatalogP5:
    @pytest.mark.django_db
    def test_catalog_returns_models_environments_integrations(
        self, api_key_client, workspace, agent_infra_project, catalog_root, monkeypatch
    ):
        seed_catalog(catalog_root)
        monkeypatch.setenv("AGENT_CATALOG_PATH", str(catalog_root))
        catalog_module._catalog_service = None

        response = api_key_client.get(
            catalog_url(workspace.slug, agent_infra_project.id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "available"
        assert len(response.data["models"]) == 1
        assert len(response.data["environments"]) == 1
        assert len(response.data["integrations"]) == 1
        assert response.data["models"][0]["name"] == "gpt-4"
        assert response.data["environments"][0]["name"] == "python-dev"
        assert response.data["integrations"][0]["name"] == "plane-mcp"

    @pytest.mark.django_db
    def test_catalog_never_exposes_credential_refs(
        self, api_key_client, workspace, agent_infra_project, catalog_root, monkeypatch
    ):
        seed_catalog(catalog_root)
        monkeypatch.setenv("AGENT_CATALOG_PATH", str(catalog_root))
        catalog_module._catalog_service = None

        response = api_key_client.get(
            catalog_url(workspace.slug, agent_infra_project.id)
        )

        payload = str(response.data)
        assert "credential_ref" not in payload
        assert "credential_refs" not in payload
        assert "openai-prod" not in payload
        assert "pypi-readonly" not in payload
        assert "plane-mcp-token" not in payload

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "section,expected_name",
        [
            ("workforce", "dev-engineer"),
            ("skills", "dev-engineer"),
            ("models", "gpt-4"),
            ("environments", "python-dev"),
            ("integrations", "plane-mcp"),
        ],
    )
    def test_catalog_section_endpoints(
        self,
        api_key_client,
        workspace,
        agent_infra_project,
        catalog_root,
        monkeypatch,
        section,
        expected_name,
    ):
        seed_catalog(catalog_root)
        monkeypatch.setenv("AGENT_CATALOG_PATH", str(catalog_root))
        catalog_module._catalog_service = None

        response = api_key_client.get(
            catalog_url(workspace.slug, agent_infra_project.id, section=section)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "available"
        assert response.data["items"][0]["name"] == expected_name

    @pytest.mark.django_db
    def test_agent_model_preference_change_does_not_expand_permissions(
        self, api_key_client, workspace, agent_infra_project, catalog_root, monkeypatch
    ):
        write_agent(
            catalog_root,
            "dev-engineer.yaml",
            "\n".join(
                [
                    "name: dev-engineer",
                    "model_preference: gpt-4",
                    "description: Development agent",
                    "tools:",
                    "  - terminal",
                ]
            ),
        )
        monkeypatch.setenv("AGENT_CATALOG_PATH", str(catalog_root))
        catalog_module._catalog_service = None

        first_response = api_key_client.get(
            catalog_url(workspace.slug, agent_infra_project.id, section="workforce")
        )
        first_agent = first_response.data["items"][0]
        assert "tools" not in first_agent
        assert first_agent["model_preference"] == "gpt-4"

        write_agent(
            catalog_root,
            "dev-engineer.yaml",
            "\n".join(
                [
                    "name: dev-engineer",
                    "model_preference: claude-sonnet",
                    "description: Development agent",
                    "tools:",
                    "  - terminal",
                    "  - deployment",
                    "  - secret-vault",
                ]
            ),
        )
        catalog_module._catalog_service = None

        second_response = api_key_client.get(
            catalog_url(workspace.slug, agent_infra_project.id, section="workforce")
        )
        second_agent = second_response.data["items"][0]

        assert second_agent["model_preference"] == "claude-sonnet"
        assert set(second_agent.keys()) == set(first_agent.keys())
        assert "tools" not in second_agent
        assert second_agent["content_hash"] != first_agent["content_hash"]
