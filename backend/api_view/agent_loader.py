"""Agent 加载器 — 单例模式管理 DeepAgent 生命周期。"""



from datetime import datetime

from typing import Any, Dict, List, Optional

import uuid



from pymongo import MongoClient



from api_view.web_config import (

    MONGODB_CHECKPOINT_COLLECTION,

    MONGODB_DB_NAME,

    MONGODB_URI,

)





class AgentLoader:

    """Agent 加载器单例。"""



    _instance: Optional["AgentLoader"] = None

    _mongodb_client: Optional[MongoClient] = None

    _initialized: bool = False

    _agent = None

    _init_error: Optional[str] = None

    _MAX_FIELD_LENGTH = 500_000



    def __new__(cls):

        if cls._instance is None:

            cls._instance = super().__new__(cls)

        return cls._instance



    async def initialize(self):

        """初始化 MongoDB 并懒加载 Agent。"""

        if self._initialized and self._agent is not None:

            return self._agent



        print("[AgentLoader] 开始初始化...")



        try:

            self._mongodb_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)

            self._mongodb_client.admin.command("ping")

            print("[AgentLoader] MongoDB 连接成功")

        except Exception as exc:

            print(f"[AgentLoader] MongoDB 不可用: {exc}（Agent 仍可使用 MemorySaver）")



        try:

            from agent.main_agent import get_agent_async



            self._agent = await get_agent_async()

            self._initialized = True

            self._init_error = None

            print("[AgentLoader] Agent 初始化完成")

        except Exception as exc:

            self._init_error = str(exc)

            print(f"[AgentLoader] Agent 初始化失败: {exc}")

            raise



        return self._agent



    @property

    def agent(self):

        if self._agent is None:

            raise RuntimeError("Agent 未初始化，请先调用 initialize()")

        return self._agent



    @property

    def init_error(self) -> Optional[str]:

        return self._init_error



    def create_config(

        self,

        thread_id: Optional[str] = None,

        doctor_id: Optional[str] = None,

        **kwargs,

    ) -> Dict[str, Any]:

        return {

            "configurable": {

                "thread_id": thread_id or str(uuid.uuid4()),

                "doctor_id": doctor_id or "doctor-li",

                **kwargs,

            }

        }



    @classmethod

    def _truncate_message_fields(cls, msg: Dict[str, Any]) -> Dict[str, Any]:

        for field in ("text", "content", "args"):

            if (

                field in msg

                and isinstance(msg[field], str)

                and len(msg[field]) > cls._MAX_FIELD_LENGTH

            ):

                msg[field] = msg[field][: cls._MAX_FIELD_LENGTH] + "\n...(已截断)"

        return msg



    async def save_display_messages(

        self, thread_id: str, messages: List[Dict[str, Any]]

    ) -> bool:

        if self._mongodb_client is None:

            return False

        try:

            db = self._mongodb_client[MONGODB_DB_NAME]

            collection = db["session_display_messages"]

            collection.delete_many({"thread_id": thread_id})

            if messages:

                now = datetime.now()

                docs = [

                    {

                        "thread_id": thread_id,

                        "index": i,

                        "message": self._truncate_message_fields(msg),

                        "updated_at": now,

                    }

                    for i, msg in enumerate(messages)

                ]

                collection.insert_many(docs)

            return True

        except Exception as exc:

            print(f"[AgentLoader] 保存展示消息失败: {exc}")

            return False



    async def get_display_messages(

        self, thread_id: str

    ) -> Optional[List[Dict[str, Any]]]:

        if self._mongodb_client is None:

            return None

        try:

            db = self._mongodb_client[MONGODB_DB_NAME]

            collection = db["session_display_messages"]

            docs = list(collection.find({"thread_id": thread_id}).sort("index", 1))

            if not docs:

                return None

            return [doc["message"] for doc in docs]

        except Exception as exc:

            print(f"[AgentLoader] 读取展示消息失败: {exc}")

            return None





agent_loader = AgentLoader()

