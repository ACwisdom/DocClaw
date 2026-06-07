"""摘要中间件工厂。"""

from typing import Union

from deepagents.middleware.summarization import create_summarization_tool_middleware
from langchain_core.language_models import BaseChatModel


def build_summarization_middleware(
    backend,
    model: Union[str, BaseChatModel],
):
    """构建 compact_conversation 摘要工具中间件。"""
    return create_summarization_tool_middleware(model=model, backend=backend)
