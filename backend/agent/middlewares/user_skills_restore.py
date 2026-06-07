"""持久化技能恢复中间件 — StoreBackend → 沙箱。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from langchain.agents.middleware import AgentMiddleware


class UserSkillsRestoreMiddleware(AgentMiddleware):
    """从 StoreBackend 恢复持久化技能到沙箱。"""

    def __init__(self, backend, skills_namespace) -> None:
        super().__init__()
        self.backend = backend
        self.namespace = skills_namespace

    async def abefore_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        store = runtime.store
        files = await self._collect_skills(store)
        if files:
            upload = getattr(self.backend, "aupload_files", None)
            if upload:
                await upload(files)
            else:
                self.backend.upload_files(files)
        return None

    def before_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        return None

    async def _collect_skills(self, store) -> List[Tuple[str, bytes]]:
        files: List[Tuple[str, bytes]] = []
        try:
            items = await store.asearch(self.namespace)
        except Exception:
            return files

        for item in items:
            key = str(item.key).lstrip("/")
            parts = key.split("/", 1)
            if len(parts) != 2:
                continue
            scope, rest = parts
            sandbox_path = f"/skills/{scope}/{rest}"
            content = item.value
            if isinstance(content, dict):
                content = content.get("content", "")
            if isinstance(content, str):
                content = content.encode("utf-8")
            if content:
                files.append((sandbox_path, content))

        return files
