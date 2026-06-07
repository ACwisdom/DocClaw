"""OpenSandbox 沙箱初始化（Phase 4 前可选）。"""

from datetime import timedelta
from pathlib import Path
from typing import List, Tuple

from agent.config import LOCAL_SKILLS_DIR, SANDBOX_SKILLS_ROOT


def setup_sandbox(config, sandbox_id=None, image=None):
    """
    获取或创建 OpenSandbox 沙箱。

    Phase 0 仅在 SANDBOX_DOMAIN 配置时启用；否则由 local_setup 降级。
    """
    from opensandbox import SandboxSync

    from agent.backends.custom_opensandbox import OpenSandboxBackend

    if sandbox_id:
        try:
            sandbox = SandboxSync.connect(sandbox_id, connection_config=config)
            backend = OpenSandboxBackend(sandbox=sandbox)
            _seed_files(backend)
            return backend
        except Exception:
            sandbox_id = None

    if not image:
        image = (
            "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/"
            "code-interpreter:v1.0.2"
        )

    sandbox = SandboxSync.create(
        image,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        env={"PYTHON_VERSION": "3.11"},
        resource={"cpu": "2", "memory": "4Gi"},
        timeout=timedelta(minutes=30),
        connection_config=config,
    )
    backend = OpenSandboxBackend(sandbox=sandbox)
    _seed_files(backend)
    return backend


def _seed_files(backend) -> None:
    """上传技能文件到沙箱。"""
    file_mapping: List[Tuple[Path, str]] = []
    skills_base = Path(LOCAL_SKILLS_DIR)
    if not skills_base.exists():
        return

    for skill_dir in skills_base.iterdir():
        if not skill_dir.is_dir():
            continue
        for local_file in skill_dir.rglob("*"):
            if local_file.is_file():
                rel = local_file.relative_to(skills_base).as_posix()
                sandbox_path = f"{SANDBOX_SKILLS_ROOT}/{rel}"
                file_mapping.append((local_file, sandbox_path))

    to_upload: List[Tuple[str, bytes]] = []
    for local_path, sandbox_path in file_mapping:
        if local_path.exists():
            to_upload.append((sandbox_path, local_path.read_bytes()))

    if to_upload:
        backend.upload_files(to_upload)
