"""Verify medical tools load (MCP or fallback) and patient_summary returns data."""
import asyncio
import sys

sys.path.insert(0, ".")


async def main():
    from agent.tools.mcp_client import load_medical_tools_with_fallback
    from agent.tools.medical_api_tools import MAIN_PATIENT_TOOL_NAMES, pick_tools_by_name

    tools, source = await load_medical_tools_with_fallback(max_retries=1, retry_delay=0.5)
    names = [t.name for t in tools]
    print(f"source={source} count={len(tools)}")
    print("tools:", names)

    required = {"patient_summary", "patient_get", "his_get_labs"}
    missing = required - set(names)
    if missing:
        print("FAIL missing:", missing)
        return 1

    main_tools = pick_tools_by_name(tools, MAIN_PATIENT_TOOL_NAMES)
    print("main_tools:", [t.name for t in main_tools])

    summary_tool = next(t for t in tools if t.name == "patient_summary")
    result = await summary_tool.ainvoke({})
    print("patient_summary result:", result)

    if isinstance(result, dict) and "waiting" in result:
        print("OK waiting=", result["waiting"])
        return 0
    if isinstance(result, list) and result:
        import json

        text = result[0].get("text", "") if isinstance(result[0], dict) else str(result[0])
        data = json.loads(text)
        if "waiting" in data:
            print("OK waiting=", data["waiting"])
            return 0

    print("FAIL unexpected result")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
