"""
OpenSandbox Backend 包装（Phase 4 启用）。

Phase 0 占位实现；完整实现将在接入 OpenSandbox 时补全。
"""

from pathlib import Path

from deepagents.backends import FilesystemBackend


class OpenSandboxBackend(FilesystemBackend):
    """OpenSandbox 沙箱 Backend 占位，继承 FilesystemBackend 接口。"""

    def __init__(self, sandbox=None, **kwargs):
        self.sandbox = sandbox
        super().__init__(root_dir=".", virtual_mode=True)

    def upload_files(self, files):
        """上传文件到沙箱（占位）。"""
        for path, content in files:
            dest = Path(path.lstrip("/"))
            dest.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                content = content.encode("utf-8")
            dest.write_bytes(content)

    def download_files(self, paths):
        return []
