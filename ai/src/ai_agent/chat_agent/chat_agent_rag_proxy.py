import traceback
from fastapi import Request, WebSocket
from src.database.models import get_db
from src.database.repository import WorkflowRepository
from .chat_agent_rag_interface import ChatAgentRagInterface
from .chat_agent_rag import ChatAgentRag
from src.database.repository import ChatRepository, ChatHistoryRepository, WizardRepository
from src.database.models import Chat
from typing import Dict, Any, Optional, Union
import logging


logger = logging.getLogger('satya.error')

class ChatAgentRagProxy(ChatAgentRagInterface):
    def __init__(self):
        self.db = next(get_db())  # Get the actual session from generator
        self.chat_repository = ChatRepository(self.db)
        self.chat_history_repository = ChatHistoryRepository(self.db)
        self.workflow_repository = WorkflowRepository(self.db)  # Initialize workflow repository
        self.wizard_repository = WizardRepository(self.db)  # Initialize wizard repository

    async def generate_response_socket(
        self,
        message: dict,
        websocket: WebSocket,
        hiddenQuestion=False,
        hiddenAnswer=False
    ) -> Dict[str, Any]:
        try:
            # Get or create chat session
            chat = self.__get_chat(request=None, websocket=websocket)
            
            # Send wizard body response if message type is wizard and wizard type is answer
            if message.get('type') == 'wizard' and message.get('wizard_id'):
                wizard = self.wizard_repository.get(message['wizard_id'])
                if wizard and getattr(wizard, 'wizard_type', None) == 'answer':
                    # Send wizard body as response
                    await websocket.send_json({
                        "event": "delta",
                        "message": getattr(wizard, 'context', None) or ""
                    })
                    # Add wizard response to chat history
                    self.update_chat_history(
                        {"body": getattr(wizard, 'context', None) or "", "type": "text"},
                        role="assistant",
                        websocket=websocket,
                        hidden=hiddenAnswer
                    )
                    return {
                        "status": "success",
                        "response": getattr(wizard, 'context', None) or ""
                    }
            
            
            # Store user question message in chat history
            self.update_chat_history(
                message, "user", websocket=websocket, hidden=hiddenQuestion
            )
            
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

            workflows = self.workflow_repository.get_active_workflows_flows()

            # Initialize agent with all required parameters
            agent = self.agent_factory(
                question=message['body'],
                history=formatted_history,
                websocket=websocket,
                workflows=workflows
            )

            # Generate response
            response = await agent.generate_response_socket()
            
            print(response)

            # Store AI response in chat history
            if isinstance(response, list):
                for resp in response:
                    self.update_chat_history(
                        resp, role="assistant", websocket=websocket, hidden=hiddenAnswer
                    )
            else:
                # If response is a single string, store it directly
                self.update_chat_history(
                    response, role="assistant", websocket=websocket, hidden=hiddenAnswer
                )
            
            return {
                "status": "success",
                "response": response
            }
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            return {"status": "error", "error": str(e)}
        
    def agent_factory(self,question, history, websocket, workflows):
        return ChatAgentRag(
            question=question,
            history=history,
            websocket=websocket,
            workflows=workflows,
            db=self.db
        )

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
    def update_chat_history(
        self,
        message: Union[dict, str, list[str]],
        role: str,
        request: Optional[Request] = None,
        websocket: Optional[WebSocket] = None,
        hidden=False,
    ) -> None:
        try:
            chat = self.__get_chat(request, websocket)  # Retrieve existing chat
            
            # Convert single message to list for consistent handling
            messages = [message] if isinstance(message, (str, dict)) else message
            
            # Create a chat history entry for each message
            for msg in messages:
                if not msg:
                    continue
                
                chat_history_data = {
                    "chat_id": chat.id,
                    "body": message['body'] if isinstance(message, dict) else message,
                    "role": role,
                    "hidden": hidden,
                    "type": message['type'] if isinstance(message, dict) else "text"
                }
                
                # Add to database
                self.chat_history_repository.create(chat_history_data)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in update chat history: {str(e)} Message is {messages} :\n%s", traceback.format_exc())
            raise e