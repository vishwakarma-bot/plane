# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

FRONTMATTER_PATTERN = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", re.DOTALL)
CACHE_TTL_SECONDS = 60

_catalog_service = None


def get_catalog_service() -> "AgentCatalogService | None":
    """Return a cached service instance when AGENT_CATALOG_PATH is configured."""
    global _catalog_service

    catalog_path = os.environ.get("AGENT_CATALOG_PATH")
    if not catalog_path:
        return None

    if _catalog_service is None or _catalog_service.catalog_path != catalog_path:
        _catalog_service = AgentCatalogService(catalog_path)

    return _catalog_service


class AgentCatalogService:
    """Read-only catalog of agent YAML and skill SKILL.md definitions."""

    def __init__(self, catalog_path: str):
        self.catalog_path = catalog_path
        self._cache: dict | None = None
        self._cache_time: str | None = None
        self._cache_timestamp: float | None = None
        self._file_mtimes: dict[str, float] = {}

    def get_agents(self) -> list[dict]:
        self._ensure_cache()
        return self._cache["agents"] if self._cache else []

    def get_skills(self) -> list[dict]:
        self._ensure_cache()
        return self._cache["skills"] if self._cache else []

    def get_catalog(self) -> dict:
        root = self._catalog_root()
        if not root.is_dir():
            return {
                "status": "unavailable",
                "message": f"Agent catalog path does not exist: {self.catalog_path}",
                "catalog_path": self.catalog_path,
            }

        self._ensure_cache()
        agents = self.get_agents()
        skills = self.get_skills()
        has_errors = any(entry.get("status") == "error" for entry in agents + skills)

        return {
            "agents": agents,
            "skills": skills,
            "catalog_path": self.catalog_path,
            "last_refreshed": self._cache_time,
            "status": "stale" if has_errors else "available",
        }

    def _catalog_root(self) -> Path:
        return Path(self.catalog_path)

    def _ensure_cache(self) -> None:
        if not self._is_cache_valid():
            self._refresh_cache()

    def _is_cache_valid(self) -> bool:
        if self._cache is None or self._cache_timestamp is None:
            return False

        if time.time() - self._cache_timestamp >= CACHE_TTL_SECONDS:
            return False

        return self._collect_file_mtimes() == self._file_mtimes

    def _collect_file_mtimes(self) -> dict[str, float]:
        root = self._catalog_root()
        mtimes: dict[str, float] = {}

        agents_dir = root / "agents"
        if agents_dir.is_dir():
            for yaml_path in agents_dir.glob("*.yaml"):
                mtimes[str(yaml_path)] = yaml_path.stat().st_mtime

        skills_dir = root / "skills"
        if skills_dir.is_dir():
            for skill_path in skills_dir.glob("*/SKILL.md"):
                mtimes[str(skill_path)] = skill_path.stat().st_mtime

        return mtimes

    def _refresh_cache(self) -> None:
        self._cache = {
            "agents": self._load_agents(),
            "skills": self._load_skills(),
        }
        self._cache_time = datetime.now(timezone.utc).isoformat()
        self._cache_timestamp = time.time()
        self._file_mtimes = self._collect_file_mtimes()

    def _load_agents(self) -> list[dict]:
        agents: list[dict] = []
        agents_dir = self._catalog_root() / "agents"
        if not agents_dir.is_dir():
            return agents

        for yaml_path in sorted(agents_dir.glob("*.yaml")):
            rel_path = str(yaml_path.relative_to(self._catalog_root()))
            try:
                raw_text = yaml_path.read_text(encoding="utf-8")
            except OSError as exc:
                agents.append({"path": rel_path, "status": "error", "error": str(exc)})
                continue

            try:
                data = yaml.safe_load(raw_text)
            except yaml.YAMLError as exc:
                agents.append({"path": rel_path, "status": "error", "error": str(exc)})
                continue

            if data is None:
                agents.append(
                    {
                        "path": rel_path,
                        "status": "error",
                        "error": "File is empty or contains no YAML document",
                    }
                )
                continue

            if not isinstance(data, dict):
                agents.append(
                    {
                        "path": rel_path,
                        "status": "error",
                        "error": "Expected a YAML mapping at the document root",
                    }
                )
                continue

            entry = dict(data)
            entry["path"] = rel_path
            entry["status"] = "ok"
            agents.append(entry)

        return agents

    def _load_skills(self) -> list[dict]:
        skills: list[dict] = []
        skills_dir = self._catalog_root() / "skills"
        if not skills_dir.is_dir():
            return skills

        for skill_path in sorted(skills_dir.glob("*/SKILL.md")):
            rel_path = str(skill_path.relative_to(self._catalog_root()))
            try:
                skills.append(self._parse_skill_file(skill_path, rel_path))
            except OSError as exc:
                skills.append({"path": rel_path, "status": "error", "error": str(exc)})

        return skills

    def _parse_skill_file(self, skill_path: Path, rel_path: str) -> dict:
        content = skill_path.read_text(encoding="utf-8")
        match = FRONTMATTER_PATTERN.match(content)
        if match is None:
            return {
                "path": rel_path,
                "status": "error",
                "error": "Missing YAML frontmatter delimited by '---' markers",
            }

        frontmatter_text = match.group(1)
        body = content[match.end() :]

        try:
            data = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            return {"path": rel_path, "status": "error", "error": str(exc)}

        if data is None:
            return {"path": rel_path, "status": "error", "error": "Frontmatter is empty"}

        if not isinstance(data, dict):
            return {
                "path": rel_path,
                "status": "error",
                "error": "Expected a YAML mapping in frontmatter",
            }

        entry = dict(data)
        entry["path"] = rel_path
        entry["summary"] = self._extract_first_paragraph(body)
        entry["status"] = "ok"
        return entry

    def _extract_first_paragraph(self, body: str) -> str:
        paragraph_lines: list[str] = []
        started = False

        for line in body.splitlines():
            stripped = line.strip()
            if not started:
                if not stripped or stripped.startswith("#"):
                    continue
                started = True

            if not stripped or stripped.startswith("#"):
                break

            paragraph_lines.append(stripped)

        return " ".join(paragraph_lines)
