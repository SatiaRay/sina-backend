from chat_agent_rag_interface import ChatAgentRagInterface
from typing import List, Dict, Any
from fastapi import WebSocket

class ChatAgentRagProxy(ChatAgentRagInterface):
    async def generate_response(self, question: str, sources = False) -> Dict[str, Any]:
        pass

    async def generate_response_socket(self, question: str, websocket: WebSocket):
        pass