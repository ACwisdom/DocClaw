"""ClawHub registry client — search, download, and parse OpenClaw skills."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

CLAWHUB_BASE = "https://clawhub.ai/api/v1"
USER_AGENT = "DocClaw/1.0 (+https://github.com/docclaw)"


@dataclass
class ParsedClawHubSkill:
    slug: str
    name: str
    description: str
    system_prompt: str
    version: str
    author: str
    publisher: str
    install_count: int
    rating: float
    tags: str
    updated_at: str
    category: str
    scenarios: str
    compatibility: str
    highlights: str


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---"):
        return {}, content.strip()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content.strip()
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, parts[2].strip()


def _infer_category(slug: str, tags: str, summary: str) -> str:
    text = f"{slug} {tags} {summary}".lower()
    if any(k in text for k in ("pubmed", "research", "literature", "trial", "文献", "科研", "指南")):
        return "research"
    if any(k in text for k in ("patient", "consent", "education", "宣教", "沟通", "家属", "comms")):
        return "education"
    if any(k in text for k in ("document", "record", "病历", "doc", "extract", "notes")):
        return "record"
    return "clinical"


def _format_timestamp(ms: int | None) -> str:
    if not ms:
        return datetime.utcnow().strftime("%Y-%m-%d")
    return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _stars_to_rating(stars: int, downloads: int) -> float:
    base = 4.2 + min(stars, 50) * 0.01
    if downloads > 1000:
        base = min(4.9, base + 0.1)
    return round(min(5.0, max(3.5, base)), 1)


def parse_skill_md(slug: str, skill_md: str) -> tuple[str, str, str]:
    meta, body = _parse_frontmatter(skill_md)
    name = meta.get("name", slug)
    description = meta.get("description", "")
    system_prompt = body or skill_md
    return name, description, system_prompt


class ClawHubClient:
    def __init__(self, base_url: str = CLAWHUB_BASE, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        with httpx.Client(timeout=self.timeout, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(f"{self.base_url}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    def _download_bytes(self, slug: str) -> bytes:
        with httpx.Client(timeout=self.timeout, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(f"{self.base_url}/download", params={"slug": slug})
            resp.raise_for_status()
            return resp.content

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("/search", params={"q": query, "limit": limit})
        return data.get("results", [])

    def get_skill_meta(self, slug: str) -> dict[str, Any]:
        return self._get(f"/skills/{slug}")

    def download_skill_zip(self, slug: str, output_dir: Path | None = None) -> bytes:
        content = self._download_bytes(slug)
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                zf.extractall(output_dir)
        return content

    def fetch_parsed_skill(self, slug: str, save_dir: Path | None = None) -> ParsedClawHubSkill:
        meta = self.get_skill_meta(slug)
        skill_info = meta.get("skill", {})
        owner = meta.get("owner", {})
        latest = meta.get("latestVersion", {})
        stats = skill_info.get("stats", {})

        zip_bytes = self.download_skill_zip(slug, save_dir)
        skill_md = ""
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("SKILL.md"):
                    skill_md = zf.read(name).decode("utf-8")
                    break

        if not skill_md:
            raise ValueError(f"SKILL.md not found in ClawHub package: {slug}")

        name, description, system_prompt = parse_skill_md(slug, skill_md)
        summary = skill_info.get("summary") or skill_info.get("displayName") or description
        if not description:
            description = summary

        owner_handle = owner.get("displayName") or owner.get("handle") or "ClawHub 社区"
        version = latest.get("version", "v1.0")
        if version and not version.startswith("v"):
            version = f"v{version}"

        downloads = int(stats.get("downloads") or stats.get("installsAllTime") or 0)
        stars = int(stats.get("stars") or 0)
        changelog = (latest.get("changelog") or "").strip()
        highlights = changelog[:500] if changelog else "来自 ClawHub 开放技能注册表"

        from .clawhub_localizations import localize_clawhub_skill

        parsed = ParsedClawHubSkill(
            slug=slug,
            name=skill_info.get("displayName") or name,
            description=summary[:500],
            system_prompt=system_prompt[:12000],
            version=version,
            author=owner_handle,
            publisher="ClawHub",
            install_count=downloads,
            rating=_stars_to_rating(stars, downloads),
            tags=slug.replace("-", ","),
            updated_at=_format_timestamp(skill_info.get("updatedAt")),
            category=_infer_category(slug, slug, summary),
            scenarios=description[:300] if description != summary else summary[:300],
            compatibility="DocClaw 问诊工作台 / 个人技能库",
            highlights=highlights,
        )
        return localize_clawhub_skill(parsed)


DEFAULT_MEDICAL_SLUGS = [
    "medical-qa",
    "medical-document-processor",
    "medical-research-toolkit",
    "clinical-doc-assistant",
    "clinical-data-extractor",
    "ecg-ai-diagnosis",
    "pubmed-literature-search",
    "pubmed-search-skill",
    "virtual-patient-roleplay",
    "patient-consent-simplifier",
    "clinical-trial",
]
