# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import re

import pytest

from plane.agent_infra.services import catalog as catalog_module
from plane.agent_infra.services.catalog import (
    AGENT_PUBLIC_FIELDS,
    SKILL_PUBLIC_FIELDS,
    AgentCatalogService,
)

SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@pytest.fixture
def catalog_root(tmp_path):
    root = tmp_path / "agent-catalog"
    (root / "agents").mkdir(parents=True)
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


@pytest.mark.unit
class TestAgentCatalogService:
    def test_get_catalog_does_not_expose_catalog_path(self, catalog_service, catalog_root):
        write_agent(
            catalog_root,
            "dev-engineer.yaml",
            "\n".join(
                [
                    "name: dev-engineer",
                    "model_preference: gpt-4",
                    "description: Development agent",
                    "fallback_models:",
                    "  - claude-sonnet",
                    "tools:",
                    "  - terminal",
                ]
            ),
        )

        catalog = catalog_service.get_catalog()

        assert "catalog_path" not in catalog
        assert catalog["status"] == "available"

    def test_agent_entries_only_contain_allowlisted_fields(self, catalog_service, catalog_root):
        agent_content = "\n".join(
            [
                "name: dev-engineer",
                "model_preference: gpt-4",
                "description: Development agent",
                "assignment_types:",
                "  - development",
                "skills:",
                "  - skills/dev-engineer/SKILL.md",
                "fallback_models:",
                "  - claude-sonnet",
                "tools:",
                "  - terminal",
                "constraints:",
                "  no_production_access: true",
            ]
        )
        write_agent(catalog_root, "dev-engineer.yaml", agent_content)

        catalog = catalog_service.get_catalog()
        agent = catalog["agents"][0]

        assert set(agent.keys()) == set(AGENT_PUBLIC_FIELDS)
        assert agent["skills"] == ["dev-engineer"]
        assert "fallback_models" not in agent
        assert "tools" not in agent
        assert "constraints" not in agent
        assert agent["path"] == "agents/dev-engineer.yaml"
        assert not agent["path"].startswith("/")

    def test_skill_entries_only_contain_allowlisted_fields(self, catalog_service, catalog_root):
        skill_content = write_skill(
            catalog_root,
            "dev-engineer",
            "\n".join(
                [
                    "name: dev-engineer",
                    "description: Development skill",
                    "type: implementation",
                    "internal_token: secret-value",
                ]
            ),
        )

        catalog = catalog_service.get_catalog()
        skill = catalog["skills"][0]

        assert set(skill.keys()) == set(SKILL_PUBLIC_FIELDS)
        assert "internal_token" not in skill
        assert skill["path"] == "skills/dev-engineer/SKILL.md"
        assert skill["summary"] == "Skill body paragraph."
        expected_hash = hashlib.sha256(skill_content.encode("utf-8")).hexdigest()
        assert skill["content_hash"] == expected_hash

    def test_content_hash_is_valid_sha256_hex(self, catalog_service, catalog_root):
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

        catalog = catalog_service.get_catalog()

        for entry in catalog["agents"] + catalog["skills"]:
            assert SHA256_HEX_PATTERN.match(entry["content_hash"])

    def test_validation_errors_for_missing_agent_fields(self, catalog_service, catalog_root):
        write_agent(
            catalog_root,
            "invalid-agent.yaml",
            "description: Missing required fields\n",
        )

        agent = catalog_service.get_catalog()["agents"][0]

        assert agent["status"] == "ok"
        assert "Missing required field: name" in agent["validation_errors"]
        assert "Missing required field: model_preference" in agent["validation_errors"]

    def test_validation_errors_for_missing_skill_fields(self, catalog_service, catalog_root):
        write_skill(
            catalog_root,
            "invalid-skill",
            "type: implementation\n",
        )

        skill = catalog_service.get_catalog()["skills"][0]

        assert skill["status"] == "ok"
        assert "Missing required field: name" in skill["validation_errors"]
        assert "Missing required field: description" in skill["validation_errors"]

    def test_parse_errors_mark_entry_as_error(self, catalog_service, catalog_root):
        write_agent(catalog_root, "broken-agent.yaml", "name: [unclosed")

        catalog = catalog_service.get_catalog()
        agent = catalog["agents"][0]

        assert catalog["status"] == "stale"
        assert agent["status"] == "error"
        assert agent["validation_errors"]
        assert "content_hash" in agent

    def test_unavailable_catalog_does_not_expose_path(self, tmp_path, monkeypatch):
        missing_path = tmp_path / "missing-catalog"
        monkeypatch.setenv("AGENT_CATALOG_PATH", str(missing_path))
        service = AgentCatalogService(str(missing_path))

        catalog = service.get_catalog()

        assert catalog["status"] == "unavailable"
        assert "catalog_path" not in catalog
        assert str(missing_path) not in catalog.get("message", "")
