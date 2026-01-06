from typing import Dict, Any
from fastapi import WebSocket

class ChatAgentRagInterface:
    async def generate_response(self, question: str, websocket: WebSocket, access_token: str) -> Dict[str, Any]:
        pass