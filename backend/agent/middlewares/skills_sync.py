"""技能同步中间件 — 本地 skills 目录 → 沙箱。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage

from agent.config import LOCAL_SKILLS_DIR, LOCAL_WORKSPACE_DIR, SANDBOX_SKILLS_ROOT


class SkillsSyncMiddleware(AgentMiddleware):
    """将本地 skills 同步到沙箱（仅 OpenSandbox 模式）。"""

    def __init__(self, backend) -> None:
        super().__init__()
        self.backend = backend
        self._last_hashes: Dict[str, str] = {}

    def before_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        updated = self._sync_files()
        if updated:
            return self._make_notification(updated)
        return None

    async def abefore_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        import asyncio

        loop = asyncio.get_running_loop()
        updated = await loop.run_in_executor(None, self._sync_files)
        if updated:
            return self._make_notification(updated)
        return None

    def _sync_files(self) -> List[str]:
        local_dir = Path(LOCAL_SKILLS_DIR)
        if not local_dir.exists():
            return []

        updated: List[str] = []
        for skill_dir in local_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            sandbox_skill_dir = f"{SANDBOX_SKILLS_ROOT}/{skill_name}"
            files_to_upload: List[Tuple[str, bytes]] = []
            has_changes = False

            for local_file in skill_dir.rglob("*"):
                if not local_file.is_file():
                    continue
                relative = local_file.relative_to(skill_dir).as_posix()
                sandbox_path = f"{sandbox_skill_dir}/{relative}"
                content = local_file.read_bytes()
                local_hash = hashlib.md5(content).hexdigest()
                cache_key = f"{skill_name}/{relative}"
                if self._last_hashes.get(cache_key) == local_hash:
                    continue

                check = self.backend.execute(f"test -f {sandbox_path}")
                if check.exit_code == 0:
                    try:
                        results = self.backend.download_files([sandbox_path])
                        if results and results[0].content and not results[0].error:
                            remote = results[0].content
                            if isinstance(remote, str):
                                remote = remote.encode("utf-8")
                            if hashlib.md5(remote).hexdigest() == local_hash:
                                self._last_hashes[cache_key] = local_hash
                                continue
                    except Exception:
                        pass

                files_to_upload.append((sandbox_path, content))
                self._last_hashes[cache_key] = local_hash
                has_changes = True

            if has_changes and files_to_upload:
                self.backend.upload_files(files_to_upload)
                updated.append(skill_name)

        return updated

    def _make_notification(self, skill_names: List[str]) -> Dict[str, Any]:
        skills_list = "\n".join(f"- {name}" for name in skill_names)
        notice = (
            f"[系统通知] 以下技能包已更新：\n{skills_list}\n"
            "请使用 `ls /skills/` 查看详情。"
        )
        return {"messages": [SystemMessage(content=notice)]}


class LocalSkillsSyncMiddleware(AgentMiddleware):
    """本地 Backend 模式：将 skills 目录增量镜像到 agent_workspace/skills。"""

    def __init__(self) -> None:
        super().__init__()
        self._last_hashes: Dict[str, str] = {}

    def before_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        updated = self._sync_local()
        if updated:
            return self._make_notification(updated)
        return None

    async def abefore_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        import asyncio

        loop = asyncio.get_running_loop()
        updated = await loop.run_in_executor(None, self._sync_local)
        if updated:
            return self._make_notification(updated)
        return None

    def _sync_local(self) -> List[str]:
        src = Path(LOCAL_SKILLS_DIR)
        if not src.exists():
            return []

        dest_root = LOCAL_WORKSPACE_DIR / "skills"
        dest_root.mkdir(parents=True, exist_ok=True)
        updated: List[str] = []

        for skill_dir in src.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            dest_dir = dest_root / skill_name
            has_changes = False

            for local_file in skill_dir.rglob("*"):
                if not local_file.is_file():
                    continue
                relative = local_file.relative_to(skill_dir).as_posix()
                cache_key = f"{skill_name}/{relative}"
                content = local_file.read_bytes()
                local_hash = hashlib.md5(content).hexdigest()
                if self._last_hashes.get(cache_key) == local_hash:
                    continue

                target = dest_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    remote_hash = hashlib.md5(target.read_bytes()).hexdigest()
                    if remote_hash == local_hash:
                        self._last_hashes[cache_key] = local_hash
                        continue

                target.write_bytes(content)
                self._last_hashes[cache_key] = local_hash
                has_changes = True

            if has_changes:
                updated.append(skill_name)

        return updated

    def _make_notification(self, skill_names: List[str]) -> Dict[str, Any]:
        skills_list = "\n".join(f"- {name}" for name in skill_names)
        notice = (
            f"[系统通知] 本地技能已同步：\n{skills_list}\n"
            "请使用 `ls /skills/` 查看详情。"
        )
        return {"messages": [SystemMessage(content=notice)]}
