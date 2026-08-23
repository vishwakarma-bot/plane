# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import re

import pytest

from plane.agent_infra.services import catalog as catalog_module
from plane.agent_infra.services.catalog import (
    AGENT_PUBLIC_FIELDS,
    ENVIRONMENT_PUBLIC_FIELDS,
    INTEGRATION_PUBLIC_FIELDS,
    MODEL_PUBLIC_FIELDS,
    SKILL_PUBLIC_FIELDS,
    AgentCatalogService,
)

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


@pytest.mark.unit
class TestAgentCatalogServiceP5:
    def test_get_catalog_includes_all_catalog_types(self, catalog_service, catalog_root):
        write_agent(
            catalog_root,
            "dev-engineer.yaml",
            "name: dev-engineer\nmodel_preference: gpt-4\ndescription: Development agent\n",
        )
        write_skill(
            catalog_root,
            "dev-engineer",
            "name: dev-engineer\ndescription: Development skill\n",
        )
        write_model(
            catalog_root,
            "gpt-4.yaml",
            "name: gpt-4\nprovider: openai\ncapabilities:\n  - code-generation\n",
        )
        write_environment(
            catalog_root,
            "python-dev.yaml",
            "name: python-dev\ndescription: Python environment\ntoolchain:\n  - python-3.12\n",
        )
        write_integration(
            catalog_root,
            "plane-mcp.yaml",
            "name: plane-mcp\ntype: mcp\ndescription: Plane MCP integration\n",
        )

        catalog = catalog_service.get_catalog()

        assert len(catalog["agents"]) == 1
        assert len(catalog["skills"]) == 1
        assert len(catalog["models"]) == 1
        assert len(catalog["environments"]) == 1
        assert len(catalog["integrations"]) == 1

    def test_model_entries_only_contain_allowlisted_fields(self, catalog_service, catalog_root):
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
                    "constraints:",
                    "  max_tokens: 4096",
                ]
            ),
        )

        model = catalog_service.get_models()[0]

        assert set(model.keys()) == set(MODEL_PUBLIC_FIELDS)
        assert "credential_ref" not in model
        assert "constraints" not in model

    def test_environment_entries_only_contain_allowlisted_fields(
        self, catalog_service, catalog_root
    ):
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
                    "approved_commands:",
                    "  - pytest",
                ]
            ),
        )

        environment = catalog_service.get_environments()[0]

        assert set(environment.keys()) == set(ENVIRONMENT_PUBLIC_FIELDS)
        assert "credential_refs" not in environment
        assert "approved_commands" not in environment

    def test_integration_entries_only_contain_allowlisted_fields(
        self, catalog_service, catalog_root
    ):
        write_integration(
            catalog_root,
            "plane-mcp.yaml",
            "\n".join(
                [
                    "name: plane-mcp",
                    "type: mcp",
                    "description: Plane MCP integration",
                    "endpoint: mcp://plane",
                    "credential_ref: plane-mcp-token",
                ]
            ),
        )

        integration = catalog_service.get_integrations()[0]

        assert set(integration.keys()) == set(INTEGRATION_PUBLIC_FIELDS)
        assert "credential_ref" not in integration
        assert "endpoint" not in integration

    def test_content_hash_is_valid_sha256_hex_for_all_types(self, catalog_service, catalog_root):
        write_agent(
            catalog_root,
            "dev-engineer.yaml",
            "name: dev-engineer\nmodel_preference: gpt-4\n",
        )
        write_skill(
            catalog_root,
            "dev-engineer",
            "name: dev-engineer\ndescription: Development skill\n",
        )
        write_model(
            catalog_root,
            "gpt-4.yaml",
            "name: gpt-4\nprovider: openai\ncapabilities:\n  - code-generation\n",
        )
        write_environment(
            catalog_root,
            "python-dev.yaml",
            "name: python-dev\ndescription: Python environment\ntoolchain:\n  - python-3.12\n",
        )
        write_integration(
            catalog_root,
            "plane-mcp.yaml",
            "name: plane-mcp\ntype: mcp\ndescription: Plane MCP integration\n",
        )

        catalog = catalog_service.get_catalog()

        for entry in (
            catalog["agents"]
            + catalog["skills"]
            + catalog["models"]
            + catalog["environments"]
            + catalog["integrations"]
        ):
            assert SHA256_HEX_PATTERN.match(entry["content_hash"])

    def test_agent_model_preference_change_does_not_expand_capabilities(
        self, catalog_service, catalog_root
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

        first_agent = catalog_service.get_agents()[0]
        assert set(first_agent.keys()) == set(AGENT_PUBLIC_FIELDS)
        assert "tools" not in first_agent

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
                ]
            ),
        )
        catalog_service._refresh_cache()

        second_agent = catalog_service.get_agents()[0]
        assert second_agent["model_preference"] == "claude-sonnet"
        assert set(second_agent.keys()) == set(AGENT_PUBLIC_FIELDS)
        assert "tools" not in second_agent
        assert second_agent["content_hash"] != first_agent["content_hash"]

    def test_skill_entries_only_contain_allowlisted_fields(self, catalog_service, catalog_root):
        skill_content = write_skill(
            catalog_root,
            "dev-engineer",
            "name: dev-engineer\ndescription: Development skill\n",
        )

        skill = catalog_service.get_skills()[0]

        assert set(skill.keys()) == set(SKILL_PUBLIC_FIELDS)
        expected_hash = hashlib.sha256(skill_content.encode("utf-8")).hexdigest()
        assert skill["content_hash"] == expected_hash
