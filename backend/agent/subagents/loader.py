"""子 Agent 配置加载（Phase 2）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from agent.config import LOCAL_SUBAGENT_CONFIG_DIR


def load_subagent_configs(
    configs_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """从 YAML 加载子 Agent 配置。"""
    if configs_dir is None:
        configs_dir = LOCAL_SUBAGENT_CONFIG_DIR

    configs: List[Dict[str, Any]] = []
    if not configs_dir.exists():
        print(f"[WARNING] 子 Agent 配置目录不存在: {configs_dir}")
        return configs

    for yaml_file in sorted(configs_dir.glob("*.yaml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            print(f"[ERROR] 解析 YAML 失败: {yaml_file} — {exc}")
            continue
        except OSError as exc:
            print(f"[ERROR] 读取文件失败: {yaml_file} — {exc}")
            continue

        missing = _validate_subagent_config(data, yaml_file.name)
        if missing:
            print(f"[ERROR] {yaml_file.name} 缺少必填字段: {', '.join(missing)}")
            continue

        configs.append(data)
        print(f"[INFO] 已加载子 Agent 配置: {data['name']} ← {yaml_file.name}")

    return configs


def resolve_subagent_tools(
    raw_configs: List[Dict[str, Any]],
    available_tools: list,
    extra_middleware: dict | None = None,
) -> list:
    """将 YAML 工具名称解析为实际工具对象。"""
    if extra_middleware is None:
        extra_middleware = {}

    tool_index: Dict[str, object] = {}
    for tool in available_tools:
        name = getattr(tool, "name", None)
        if name:
            tool_index[name] = tool

    subagents: List[Dict[str, Any]] = []

    for config in raw_configs:
        resolved_tools = []
        for pattern in config.get("tools", []):
            matched = False
            for tool_name, tool_obj in tool_index.items():
                if pattern in tool_name or tool_name == pattern:
                    resolved_tools.append(tool_obj)
                    matched = True
            if not matched:
                print(
                    f"[WARNING] 子 Agent '{config['name']}': "
                    f"工具 '{pattern}' 未能匹配任何可用工具"
                )

        seen: set = set()
        unique_tools = []
        for tool in resolved_tools:
            name = getattr(tool, "name", id(tool))
            if name not in seen:
                seen.add(name)
                unique_tools.append(tool)

        subagent: Dict[str, Any] = {
            "name": config["name"],
            "description": config["description"].replace("\n", " ").strip(),
            "system_prompt": config["system_prompt"],
            "tools": unique_tools,
        }

        if config.get("model"):
            subagent["model"] = config["model"]
        if config.get("skills"):
            subagent["skills"] = config["skills"]
        if config.get("interrupt_on"):
            subagent["interrupt_on"] = config["interrupt_on"]

        agent_middleware = list(config.get("middleware", []))
        if config["name"] in extra_middleware:
            agent_middleware.extend(extra_middleware[config["name"]])
        if agent_middleware:
            subagent["middleware"] = agent_middleware

        subagents.append(subagent)
        print(
            f"[INFO] 子 Agent '{config['name']}' 已解析: "
            f"{len(unique_tools)} 个工具"
        )

    return subagents


def _validate_subagent_config(data: Dict[str, Any], filename: str) -> List[str]:
    """校验 SubAgent 必填字段。"""
    if not data:
        return ["(空配置)"]

    required = ["name", "description", "system_prompt", "tools"]
    missing = [field for field in required if field not in data or data[field] is None]

    tools = data.get("tools")
    if tools is not None and (not isinstance(tools, list) or len(tools) == 0):
        missing.append("tools (必须为非空列表)")

    system_prompt = data.get("system_prompt")
    if system_prompt is not None and (
        not isinstance(system_prompt, str) or not system_prompt.strip()
    ):
        missing.append("system_prompt (必须为非空字符串)")

    return missing
