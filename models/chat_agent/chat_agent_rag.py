from sys import set_coroutine_origin_tracking_depth
from agents import Runner
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv
from database.vector_store import VectorStore
from database.repository import InstructionRepository
from database.models import SessionLocal
from models.agents.title_analyzer_agent import TitleAnalyzerAgent
from util.logging_config import configure_logging, log_error
import asyncio
from fastapi import WebSocket
from openai import OpenAI
from anyio import to_thread
from .chat_agent_rag_interface import ChatAgentRagInterface
from sqlalchemy.orm import Session
from pathlib import Path
import json
import re
from models.tools.functions import call_function
from provider.service_container import container
import logging
import inspect

load_dotenv()
main_logger, error_logger, _, debug_logger = configure_logging()

# Define the instructions from the original RAG system
SATIA_INSTRUCTIONS = """

# Identity  
You are an intelligent support assistant. Your identity should be defined dynamically and customized depending on the context or organization you are serving.  

# Instructions  

* Always respond in **Persian (Farsi)**.  
* Give priority to the information explicitly provided to you. Use your own knowledge only to complement and clarify the given information.  
* If the provided information does not contain the answer, respond honestly: **"متأسفانه اطلاعات کافی برای پاسخ به این سوال ندارم."**  
* Do not guess. Only respond based on the available information.  
* Do not omit or skip relevant information. Your answer must be complete and accurate.  
* Tables written in markdown should be converted into **HTML tables** in your response.  
* Never return tables in markdown format.  
* Links written in markdown should be converted into **HTML `<a>` tags** with `href` set to the URL and `target="__blank"` so they open in a new tab.  
* Do not remove `\n` characters from the source text. Keep them for readability in the response.  
* Information provided in the **Workflows** section takes priority over information in the **Context Information** section.  

---

### Example 1  
**Context Information:**  
Service: Laleh One-Month Plan  

| Name     | Duration | Speed | International GB | Price (Toman) |  
|----------|----------|-------|------------------|---------------|  
| Laleh 1  | 1 month  | up to 20 | 65 | 134,000 |  

**User Question:**  
What are the conditions of the internet services?  

**Assistant Response:**  
<p>Our internet services are as follows:</p>  
<table>  
    <tr>  
        <th>Service Name</th>  
        <th>Duration</th>  
        <th>Speed</th>  
        <th>International GB</th>  
        <th>Price (Toman)</th>  
    </tr>  
    <tr>  
        <td>Laleh 1</td>  
        <td>1 month</td>  
        <td>20</td>  
        <td>65</td>  
        <td>134,000</td>  
    </tr>  
</table>  

---

### Example 2  
**Context Information:**  
To see the list of Satia agencies, click on this <https://satia.co/agencies>  

**User Question:**  
Where are Satia’s agencies?  

**Assistant Response:**  
To see the list of Satia agencies, click on this <a href="https://satia.co/agencies" target="__blank">link</a>.  

"""

class ChatAgentRag(ChatAgentRagInterface):
    def __init__(
            self,
            question: str,
            history: Optional[List[Dict[str, str]]] = None,
            websocket: WebSocket = None,
            workflows: Optional[str] = None,
            db: Session = SessionLocal()
        ):
        self.db = db
        self.question = question
        self.history = history
        self.websocket = websocket
        self.workflows = workflows
        
        self.vector_store = VectorStore()
        self.client = OpenAI()
        self.called_function = {
            "name": None,
            "arguments": []
        }
        main_logger.info("Initialized Agent RAG System with GPT-4")

    def _get_active_instructions(self) -> str:
        """Get active instructions from the database"""
        try:
            if not self.db:
                main_logger.warning("No database session available")
                return ""
                
            repo = InstructionRepository(self.db)
            active_instructions = repo.get_active_instructions()
            
            if not active_instructions:
                return ""
            
            instructions_text = "\n# Active Instructions from Database\n\n"
            for instruction in active_instructions:
                # Split the text into lines and add "* " prefix to each line
                formatted_text = "\n".join(f"* {line}" for line in instruction.text.split("\n"))
                instructions_text += f"{formatted_text}\n"
            
            return instructions_text
        except Exception as e:
            error_logger.error(f"Error fetching active instructions: {str(e)}")
            return ""
        
    def _get_format_context(self, documents)-> str:
        """
            Takes documetns and compose them with particular format  
        """
        context_parts = []
        for doc in documents:
            score = doc.get('score', 1.0)
            text = doc['text']
            context_parts.append(f"[Score: {score:.3f}]\n{text}")
        
        return "\n\n---\n\n".join(context_parts)

    async def get_relevant_docs(self, question: str, score: float = 1.0) -> List[Dict]:
        """
        Takes a user question and returns a list of relevant documents.
        
        Args:
            question (str): The user's question
            score (float): Minimum score required for document similarity to question
            
        Returns:
            List[Dict]: List of relevant documents with their metadata and content
        """
        try:
            main_logger.info(f"Finding relevant documents for question: {question}")
            
            # Search for relevant documents
            relevant_docs = self.vector_store.search(question)

            main_logger.debug(f"Found {len(relevant_docs)} relevant documents")
            
            filterd_ids = await self._filter_found_documents_by_agent(question, relevant_docs)
            
            main_logger.info(f"Found documetns after filter by AI length is {len(filterd_ids)}")
            
            if len(filterd_ids):
            
                # Filter and return the relevant documents
                filtered_docs = [
                    doc for doc in relevant_docs 
                    if doc['id'] in filterd_ids
                ]
                
                return sorted(filtered_docs, key=lambda x: x.get('score', set_coroutine_origin_tracking_depth))
            
            return []
            
        except Exception as e:
            error_context = f"Question: {question}"
            log_error(error_logger, e, error_context)
            raise 
        
    async def _filter_found_documents_by_agent(self, question, documents) -> list[int]:
        """
        Takes found relevent docs in vector db and filter them according user question using AI model
        """
        # Create a document title analyzer agent
        title_analyzer = TitleAnalyzerAgent()
        
        # Prepare the input for the agent
        titles_info = "\n".join([
            f"ID: {doc['id']} - Title: {doc['metadata'].get('title', 'Untitled')}"
            for doc in documents
        ])
        
        agent_input = f"""User Question: {question}

        Available Documents:
        {titles_info}

        Please return only the IDs of the documents that are most relevant to answering the question, as a comma-separated list."""
        
        # Get the agent's response
        result = await Runner.run(title_analyzer, input=agent_input)
        
        # Parse the response to get the IDs
        selected_ids = [id.strip() for id in result.final_output.split(',')]
        
        return selected_ids

    def _format_chat_history(self) -> List[Dict[str, str]]:
        """
        Format chat history into a list of messages with role and content.
        
        Returns:
            List[Dict[str, str]]: List of formatted messages with role and content
        """
        if not self.history:
            return []
        
        formatted_messages = []
        for msg in self.history:
            if isinstance(msg, str):
                # If it's a string, try to parse it as JSON
                try:
                    msg = json.loads(msg)
                except json.JSONDecodeError:
                    # If it's not valid JSON, treat it as a regular message
                    formatted_messages.append({
                        "role": "user",
                        "content": msg
                    })
                    continue
            
            if isinstance(msg, dict):
                if msg.get('type'):
                    # Handle special message types (like function calls)
                    formatted_messages.append({
                        "role": "developer",
                        "content": json.dumps(msg)
                    })
                else:
                    # Handle regular messages
                    role = msg.get('role', 'user')
                    content = msg.get('body', '')
                    formatted_messages.append({
                        "role": role,
                        "content": content
                    })
        
        return formatted_messages
    
    async def _compose_prompt(self):
        # Search for relevant documents
        relevant_docs = await self.get_relevant_docs(self.question, 1.0)
        
        # Format context with scores
        context = self._get_format_context(relevant_docs)
        
        # Format chat history
        formatted_history = self._format_chat_history()
        
        workflows_text = f"# Workflows\n\n{self.workflows}\n" if self.workflows else ""
        
        # Get active instructions from database
        active_instructions = self._get_active_instructions()
        
        # Prepare the input prompt
        prompt = [
            {
                "role": "developer",
                "content": f"""# Instructions

                {SATIA_INSTRUCTIONS}

                {active_instructions}

                # {workflows_text}

                Context Information:
                {context}"""
            }
        ]
        
        # Add chat history messages
        prompt.extend(formatted_history)
        
        # Add the current question
        prompt.append({
            "role": "user",
            "content": self.question
        })
        
        return prompt
    
    def _connect_stream(self, messages: List[Dict[str, str]]):
        """Stream response from OpenAI with tools configuration"""
        try:
            tools = self._load_tools_configuration()
            settings = container.make('settings')
            model = settings.text_agent_model or os.getenv("GPT_MODEL")
            return self.client.responses.create(
               model=model,
               input=messages,
               stream=True,
               tools=tools
            )
        except Exception as e:
            error_logger.error(f"Error in _connect_stream: {str(e)}")
            raise

    async def generate_response_socket(self, broadcast_response_to_websocket = True):
        try:
            main_logger.info(f"Generating response for question: {self.question}")

            prompt = await self._compose_prompt()
            
            # In your async function:
            stream = await to_thread.run_sync(self._connect_stream, prompt)

            print("Start to listening to Agent events ...", flush=True)
            
            response = await self._stream_event_handler(stream=stream, broadcast_response_to_websocket=broadcast_response_to_websocket)
                    
            if response['call_info'] is not None:
                # If a function was called, handle it and get the new response
                subResponse = await self._suplly_called_function(response['call_info'])
                
                response['text'] += subResponse
            
            return response['text']
            
        except Exception as e:
            error_context = f"Question: {self.question}"
            log_error(error_logger, e, error_context)
            raise
        
    async def _stream_event_handler(self, stream, broadcast_response_to_websocket) -> dict:
        """
            Listense to stream events and handles them
        """
        result = {
            "call_info": None,
            "text": ""
        }
        
        for event in stream:
            # Handle function call events
            if event.type == 'response.output_item.done':
                if event.item.type == 'function_call':
                    result['call_info']  = {
                        "type": "function_call",
                        "id" : event.item.id,
                        "call_id": event.item.id,
                        "name": event.item.name,
                        "arguments": event.item.arguments,
                    }
                    
                    if broadcast_response_to_websocket:
                        # broadcast Agent call function event response to client
                        await self.websocket.send_json(data={
                            'event': 'fetching data',
                            'message': "در حال واکشی اطلاعات, لطفا صبر کنید."
                        })
                    break
            
            # Handle regular text output
            if event.type == 'response.output_text.delta':
                delta = event.delta
                result['text'] += delta
                
                if broadcast_response_to_websocket:
                    # broadcast Agent delta text response to client
                    await self.websocket.send_json(data={
                        'event': 'delta',
                        'message': delta,
                    })
                delay = str(os.getenv('GPT_RESPONSE_STREAM_SLEEP_SECOND', "0.0001"))
                await asyncio.sleep(float(delay))
          
        return result
        
    async def _suplly_called_function(self, called_function: dict):
        try:
            # Add function call to history
            self.history.append(called_function)
            
            # Call the function and get result
            result = await call_function(called_function['name'], json.loads(called_function['arguments']), client_websocket_connection=self.websocket)
            
            # Add result to chat history
            if self.history is None:
                self.history = []
            
            self.history.append({
                "type": "function_call_output",
                "call_id": called_function['call_id'],
                "output": json.dumps(result)
            })
            
        except Exception as e:
            error_logger.error(f"Error in supply_called_function: {str(e)}")
            
            # Add error information to chat history
            if self.history is None:
                self.history = []
            
            error_info = {
                "status": "error",
                "function": called_function['name'],
                "error": str(e)
            }
            
            self.history.append({
                "type": "function_call_output",
                "call_id": called_function['call_id'],
                "output": json.dumps(error_info)
            })
            
        finally:
            # Reset called_function regardless of success or failure
            called_function = {
                "name": None,
                "arguments": []
            }
            # Re-call generate_response_socket with updated history
            return await self.generate_response_socket()

    def _load_tools_configuration(self) -> List[Dict]:
        """
        Load and return the tools configuration from map.json.
        Validates that function names match the required pattern ^[a-zA-Z0-9_-]+$
        
        Returns:
            List[Dict]: List of function configurations from the map file
            
        Raises:
            FileNotFoundError: If the map.json file is not found
            json.JSONDecodeError: If the map.json file contains invalid JSON
            ValueError: If any function name doesn't match the required pattern
        """
        try:
            map_path = Path(__file__).parent.parent / "tools" / "functions" / "map.json"
            with open(map_path, 'r', encoding='utf-8') as f:
                tools_config = json.load(f)
            
            # Validate function names
            name_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
            for func in tools_config["functions"]:
                if not name_pattern.match(func["name"]):
                    raise ValueError(
                        f"Invalid function name '{func['name']}'. "
                        "Function names must contain only letters, numbers, underscores, and hyphens."
                    )
            
            return tools_config["functions"]
        except FileNotFoundError as e:
            error_logger.error(f"Tools configuration file not found: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            error_logger.error(f"Invalid JSON in tools configuration file: {str(e)}")
            raise
        except ValueError as e:
            error_logger.error(f"Invalid function configuration: {str(e)}")
            raise
        except Exception as e:
            error_logger.error(f"Error loading tools configuration: {str(e)}")
            raise