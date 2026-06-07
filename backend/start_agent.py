"""
DocClaw Harness 启动脚本 — 同时启动 MCP Server (:8001) 与 Agent API (:8090)。

用法:
    cd backend
    py -3.11 start_agent.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request


def _backend_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _env() -> dict:
    env = os.environ.copy()
    backend = _backend_dir()
    env["PYTHONPATH"] = backend + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _stream_output(proc: subprocess.Popen, prefix: str) -> None:
    if proc.stdout is None:
        return
    for line in proc.stdout:
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").rstrip()
        try:
            print(f"[{prefix}] {text}")
        except UnicodeEncodeError:
            safe = text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            )
            print(f"[{prefix}] {safe}")


def _wait_url(url: str, name: str, timeout: int = 120) -> bool:
    print(f"[System] 等待 {name} 就绪 ({url})...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    print(f"[System] {name} 已就绪")
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _verify_agent_routes() -> bool:
    """确认 /api/agent/chat 已注册，避免旧 uvicorn 进程仍占用端口。"""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8090/openapi.json", timeout=5) as resp:
            import json

            paths = json.loads(resp.read().decode("utf-8")).get("paths", {})
            if "/api/agent/chat" in paths:
                print("[System] Agent 对话路由已注册")
                return True
            print("[ERROR] :8090 缺少 /api/agent/chat，可能仍有旧 Agent 进程")
            print("[ERROR] 请关闭占用 8090 的窗口后重新运行 start_agent.py")
            return False
    except Exception as exc:
        print(f"[ERROR] 无法验证 Agent 路由: {exc}")
        return False


def main() -> None:
    print("=" * 60)
    print("       DocClaw DeepAgents Harness Launcher")
    print("=" * 60)
    print("  MCP Server  : http://127.0.0.1:8001/mcp")
    print("  Agent API   : http://127.0.0.1:8090")
    print("=" * 60)

    backend = _backend_dir()
    env = _env()
    procs: list[subprocess.Popen] = []

    def cleanup():
        print("\n[System] 正在停止 Harness 进程...")
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("[System] 已全部停止")

    def handle_signal(sig, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    mcp_proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server_main"],
        cwd=backend,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    procs.append(mcp_proc)
    threading.Thread(target=_stream_output, args=(mcp_proc, "MCP"), daemon=True).start()

    from agent.tools.mcp_client import wait_mcp_ready

    if not wait_mcp_ready(timeout=120):
        print("[ERROR] MCP Server 未在 120s 内就绪，请检查上方 [MCP] 日志")
        cleanup()
        sys.exit(1)
    print("[System] MCP Server 已就绪，正在启动 Agent API...")

    agent_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api_view.web_main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8090",
        ],
        cwd=backend,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    procs.append(agent_proc)
    threading.Thread(
        target=_stream_output, args=(agent_proc, "AgentAPI"), daemon=True
    ).start()

    ok_agent = _wait_url("http://127.0.0.1:8090/health", "Agent API", timeout=180)
    if not ok_agent or not _verify_agent_routes():
        print("[ERROR] Agent API 启动异常，请检查上方日志")
        cleanup()
        sys.exit(1)

    print()
    print("Harness 已启动。按 Ctrl+C 停止。")
    print("  Agent API 文档: http://127.0.0.1:8090/docs")
    print()

    try:
        while True:
            for proc in procs:
                if proc.poll() is not None:
                    print(f"[ERROR] 进程退出 code={proc.returncode}")
                    cleanup()
                    sys.exit(proc.returncode or 1)
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
