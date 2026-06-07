"""MCP 工具公共 HTTP 辅助函数。"""

from typing import Any


async def api_get(ctx, path: str, params: dict | None = None) -> Any:
    client = ctx.request_context.lifespan_context["http_client"]
    try:
        resp = await client.get(path, params=_clean_params(params))
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


async def api_post(ctx, path: str, json_body: dict | None = None) -> Any:
    client = ctx.request_context.lifespan_context["http_client"]
    try:
        resp = await client.post(path, json=json_body or {})
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


def _clean_params(params: dict | None) -> dict | None:
    if not params:
        return None
    return {k: v for k, v in params.items() if v is not None}
