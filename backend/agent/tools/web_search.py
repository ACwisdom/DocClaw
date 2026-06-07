"""网络搜索工具（智谱搜狗 API，无密钥时降级为提示）。"""

from langchain_core.tools import tool

from agent.env_utils import ZHIPU_API_KEY


@tool("web_search", parse_docstring=True)
def web_search(query: str) -> str:
    """
    使用 Web 搜索获取医学文献、指南或公开资讯。

    Args:
        query: 搜索关键词或问题。

    Returns:
        搜索结果摘要文本。
    """
    if not ZHIPU_API_KEY:
        return (
            "Web 搜索未配置（缺少 ZHIPU_API_KEY）。"
            "请改用 skill_list 查找本地技能，或使用 patient/his 工具查询患者数据。"
        )

    try:
        from zai import ZhipuAiClient

        client = ZhipuAiClient(api_key=ZHIPU_API_KEY)
        response = client.web_search.web_search(
            search_engine="search_pro",
            search_query=query,
            count=3,
            search_recency_filter="noLimit",
        )
        if response.search_result:
            return "\n\n".join(d.content for d in response.search_result)
        return "没有搜索到任何内容。"
    except Exception as exc:
        return f"搜索失败: {exc}"
