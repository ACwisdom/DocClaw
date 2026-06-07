"""

DocClaw 医疗 MCP Server 入口。



Phase 1：patient / consult / followup / skill / notification / his 工具。

"""



from fastmcp import FastMCP



from mcp_server.http_base import mcp_lifespan

from mcp_server.server_config import MCP_HOST, MCP_PATH, MCP_PORT

from mcp_server.tools.consult_tools import register_consult_tools

from mcp_server.tools.followup_tools import register_followup_tools

from mcp_server.tools.his_tools import register_his_tools

from mcp_server.tools.notification_tools import register_notification_tools

from mcp_server.tools.patient_tools import register_patient_tools

from mcp_server.tools.skill_tools import register_skill_tools



mcp = FastMCP(

    name="DocClaw-Medical-MCP-Server",

    instructions="DocClaw 医疗业务 API 工具集，将 FastAPI :8000 端点工具化",

    version="0.1.0",

    lifespan=mcp_lifespan,

)



register_patient_tools(mcp)

register_consult_tools(mcp)

register_followup_tools(mcp)

register_skill_tools(mcp)

register_notification_tools(mcp)

register_his_tools(mcp)





@mcp.tool()

async def mcp_health() -> dict:

    """MCP 服务健康检查。"""

    return {"status": "ok", "service": "docclaw-mcp", "tool_groups": 6}





def main():

    mcp.run(

        transport="streamable-http",

        host=MCP_HOST,

        port=MCP_PORT,

        path=MCP_PATH,

    )





if __name__ == "__main__":

    main()

