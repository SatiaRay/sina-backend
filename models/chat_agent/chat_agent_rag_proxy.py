from fastapi import Request, Depends,WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from database.models import get_db
from .chat_agent_rag_interface import ChatAgentRagInterface
from .chat_agent_rag import ChatAgentRag
from database.repository import ChatRepository, ChatHistoryRepository
from database.models import Chat, ChatHistory
from typing import List, Dict, Any, Optional
import json
import asyncio


class ChatAgentRagProxy(ChatAgentRagInterface):
    def __init__(self):
        self.db = next(get_db())  # Get the actual session from generator
        self.chat_repository = ChatRepository(self.db)
        self.chat_history_repository = ChatHistoryRepository(self.db)
        self.agent = ChatAgentRag()

    async def generate_response(self, question: str, sources=False, request: Optional[Request] = None) -> Dict[str, Any]:
        # Store user question message in chat history
        self.__update_chat_history(question, "user", request)

        try:
            res = await self.agent.generate_response(question, sources)
            return {
                "status": "success",
                "response": res
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def generate_response_socket(self, question: str, websocket: WebSocket) -> Dict[str, Any]:
        # Store user question message in chat history
        self.__update_chat_history(question, "user", websocket=websocket)

        print("Chat history has been updated !")

        try:
            # Get or create chat session
            chat = self.__get_chat(request=None, websocket=websocket)
            
            # Get chat history
            chat_history = self.chat_history_repository.get_chat_history_by_chat_id(chat_id=chat.id, limit=50)

            # Format messages for the agent
            formatted_history = [
                {
                    "role": msg.role,
                    "body": msg.body
                }
                for msg in chat_history
            ]

            # Generate response with history
            response = await self.agent.generate_response_socket(question, websocket, history=formatted_history)
            
            # Store AI response in chat history
            self.__update_chat_history(response, role="assistant", websocket=websocket)
            
            return response
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.__update_chat_history(error_msg, role="assistant", websocket=websocket)
            return {
                "status": "error",
                "error": str(e)
            }

    # Get or create chat session
    def __get_chat(self, request: Optional[Request] = None, websocket: Optional[WebSocket] = None) -> Chat:
        try:
            # Get session ID from request or websocket
            session_id = None
            if request:
                session_id = request.query_params.get('session_id')
            elif websocket:
                session_id = websocket.query_params.get('session_id')
            
            if not session_id:
                raise ValueError("Session ID is required")
            
            # Try to get existing chat
            chat = self.chat_repository.get_with_messages(session_id)
            
            # Create new chat if not exists
            if not chat:
                chat_data = {
                    "session_id": session_id
                }
                chat = self.chat_repository.create(chat_data)
                self.db.commit()
            
            return chat
            
        except Exception as e:
            self.db.rollback()
            raise e

    # Store new chat history message
    def __update_chat_history(self, message: str, role: str, request: Optional[Request] = None, websocket: Optional[WebSocket] = None) -> None:
        try:
            chat = self.__get_chat(request, websocket)  # Retrieve existing chat
            
            # Create new chat history entry
            chat_history_data = {
                "chat_id": chat.id,
                "body": message,
                "role": role
            }
            
            # Add to database
            self.chat_history_repository.create(chat_history_data)
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            raise e

