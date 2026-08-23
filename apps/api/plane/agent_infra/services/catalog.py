# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

FRONTMATTER_PATTERN = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", re.DOTALL)
CACHE_TTL_SECONDS = 60

AGENT_PUBLIC_FIELDS = (
    "name",
    "description",
    "model_preference",
    "assignment_types",
    "skills",
    "status",
    "path",
    "content_hash",
    "validation_errors",
)
SKILL_PUBLIC_FIELDS = (
    "name",
    "description",
    "type",
    "summary",
    "status",
    "path",
    "content_hash",
    "validation_errors",
)

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
                "message": "Agent catalog path does not exist",
            }

        self._ensure_cache()
        agents = self.get_agents()
        skills = self.get_skills()
        has_errors = any(entry.get("status") == "error" for entry in agents + skills)

        return {
            "agents": agents,
            "skills": skills,
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
                agents.append(self._build_error_entry(rel_path, str(exc)))
                continue

            try:
                data = yaml.safe_load(raw_text)
            except yaml.YAMLError as exc:
                agents.append(
                    self._build_error_entry(rel_path, str(exc), raw_text=raw_text)
                )
                continue

            if data is None:
                agents.append(
                    self._build_error_entry(
                        rel_path,
                        "File is empty or contains no YAML document",
                        raw_text=raw_text,
                    )
                )
                continue

            if not isinstance(data, dict):
                agents.append(
                    self._build_error_entry(
                        rel_path,
                        "Expected a YAML mapping at the document root",
                        raw_text=raw_text,
                    )
                )
                continue

            agents.append(self._build_public_agent_entry(data, rel_path, raw_text))

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
                skills.append(self._build_error_entry(rel_path, str(exc)))

        return skills

    def _parse_skill_file(self, skill_path: Path, rel_path: str) -> dict:
        raw_text = skill_path.read_text(encoding="utf-8")
        match = FRONTMATTER_PATTERN.match(raw_text)
        if match is None:
            return self._build_error_entry(
                rel_path,
                "Missing YAML frontmatter delimited by '---' markers",
                raw_text=raw_text,
            )

        frontmatter_text = match.group(1)
        body = raw_text[match.end() :]

        try:
            data = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            return self._build_error_entry(rel_path, str(exc), raw_text=raw_text)

        if data is None:
            return self._build_error_entry(
                rel_path,
                "Frontmatter is empty",
                raw_text=raw_text,
            )

        if not isinstance(data, dict):
            return self._build_error_entry(
                rel_path,
                "Expected a YAML mapping in frontmatter",
                raw_text=raw_text,
            )

        summary = self._extract_first_paragraph(body)
        return self._build_public_skill_entry(data, rel_path, raw_text, summary)

    def _build_public_agent_entry(self, data: dict, rel_path: str, raw_text: str) -> dict:
        validation_errors = self._validate_agent(data)
        entry = {
            "name": data.get("name"),
            "description": data.get("description"),
            "model_preference": data.get("model_preference"),
            "assignment_types": data.get("assignment_types"),
            "skills": self._normalize_skill_names(data.get("skills")),
            "status": "ok",
            "path": rel_path,
            "content_hash": self._content_hash(raw_text),
            "validation_errors": validation_errors,
        }
        return self._pick_public_fields(entry, AGENT_PUBLIC_FIELDS)

    def _build_public_skill_entry(
        self, data: dict, rel_path: str, raw_text: str, summary: str
    ) -> dict:
        validation_errors = self._validate_skill(data)
        entry = {
            "name": data.get("name"),
            "description": data.get("description"),
            "type": data.get("type"),
            "summary": summary,
            "status": "ok",
            "path": rel_path,
            "content_hash": self._content_hash(raw_text),
            "validation_errors": validation_errors,
        }
        return self._pick_public_fields(entry, SKILL_PUBLIC_FIELDS)

    def _build_error_entry(
        self, rel_path: str, error: str, raw_text: str | None = None
    ) -> dict:
        entry = {
            "path": rel_path,
            "status": "error",
            "validation_errors": [error],
        }
        if raw_text is not None:
            entry["content_hash"] = self._content_hash(raw_text)
        return entry

    def _validate_agent(self, data: dict) -> list[str]:
        errors: list[str] = []
        if not data.get("name"):
            errors.append("Missing required field: name")
        if not data.get("model_preference"):
            errors.append("Missing required field: model_preference")
        return errors

    def _validate_skill(self, data: dict) -> list[str]:
        errors: list[str] = []
        if not data.get("name"):
            errors.append("Missing required field: name")
        if not data.get("description"):
            errors.append("Missing required field: description")
        return errors

    def _normalize_skill_names(self, skills: object) -> list[str]:
        if not isinstance(skills, list):
            return []

        names: list[str] = []
        for item in skills:
            if not isinstance(item, str):
                continue

            path = Path(item)
            if path.name.lower() == "skill.md":
                names.append(path.parent.name)
            elif len(path.parts) >= 2 and path.parts[0] == "skills":
                names.append(path.parts[1])
            else:
                names.append(path.stem or item)
        return names

    def _content_hash(self, raw_text: str) -> str:
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    def _pick_public_fields(self, entry: dict, allowed_fields: tuple[str, ...]) -> dict:
        return {field: entry[field] for field in allowed_fields if field in entry}

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
