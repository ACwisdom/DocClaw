"""本地 Backend 降级（无 OpenSandbox 时使用）。"""

from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend, StoreBackend

from agent.config import (
    LOCAL_AGENTS_MD,
    LOCAL_SKILLS_DIR,
    LOCAL_WORKSPACE_DIR,
    SANDBOX_SKILLS_ROOT,
    SKILLS_STORE_NAMESPACE,
)


def setup_local_backend():
    """
    Phase 0 降级方案：使用 FilesystemBackend + StateBackend 替代 OpenSandbox。

    Returns:
        CompositeBackend 工厂函数所需的 backend 实例包装。
    """
    workspace = LOCAL_WORKSPACE_DIR
    workspace.mkdir(parents=True, exist_ok=True)
    skills_dir = workspace / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # 同步 AGENTS.md 到 workspace 根
    if LOCAL_AGENTS_MD.exists():
        agents_dest = workspace / "AGENTS.md"
        agents_dest.write_text(LOCAL_AGENTS_MD.read_text(encoding="utf-8"), encoding="utf-8")

    # 播种本地 skills 目录（若存在）
    if LOCAL_SKILLS_DIR.exists():
        _mirror_skills(LOCAL_SKILLS_DIR, skills_dir)

    fs_backend = FilesystemBackend(root_dir=str(workspace), virtual_mode=True)

    def backend_factory(rt):
        return CompositeBackend(
            default=fs_backend,
            routes={
                "/memories/": StoreBackend(
                    runtime=rt,
                    namespace=lambda rt: (
                        getattr(rt.context, "doctor_id", "doctor-li"),
                    ),
                ),
                "/persisted-skills/": StoreBackend(
                    runtime=rt,
                    namespace=lambda rt: SKILLS_STORE_NAMESPACE,
                ),
                SANDBOX_SKILLS_ROOT + "/": fs_backend,
            },
        )

    return backend_factory


def _mirror_skills(src: Path, dest: Path) -> None:
    """将本地 skills 目录镜像到 workspace/skills。"""
    import shutil

    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(item, target)
