from typing import Dict, Any
from fastapi import WebSocket

class ChatAgentRagInterface:
    async def generate_response(self, question: str, sources = False) -> Dict[str, Any]:
        pass

    async def generate_response_socket(self, question: str, websocket: WebSocket) -> Dict[str, Any]:
        pass