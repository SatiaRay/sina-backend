from agents import Agent, Runner
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
from database.vector_store import VectorStore
from database.repository import InstructionRepository
from database.models import SessionLocal
from models.agents.title_analyzer_agent import TitleAnalyzerAgent
import logging
from util.logging_config import configure_logging, log_error
import asyncio
from fastapi import WebSocket, Depends
from openai import OpenAI
from anyio import to_thread
from .chat_agent_rag_interface import ChatAgentRagInterface
from sqlalchemy.orm import Session
from pathlib import Path
import json
import re
from models.tools.functions import call_function

load_dotenv()
main_logger, error_logger, api_logger = configure_logging()

# Define the instructions from the original RAG system
SATIA_INSTRUCTIONS = """

#Identity

شما یک دستیار هوشمند پشتیبانی ساتیا به زبان فارسی هستید. وظیفه شما پاسخ دادن به سوالات کاربران با استفاده از اطلاعاتی است که در اختیار شما قرار داده شده است.

#Instructions

* همیشه به زبان فارسی پاسخ دهید.
* اطلاعات ارائه شده را بر دانش خود مقدم بدانید و از دانش خود فقط برای تکمیل و واضح تر کردن پاسخ استفاده کنید
* اگر پاسخ سوال در اطلاعات ارائه شده موجود نیست، صادقانه بگویید: "متأسفانه اطلاعات کافی برای پاسخ به این سوال ندارم."
* از حدس و گمان خودداری کنید و فقط بر اساس اطلاعات موجود پاسخ دهید.
* از فاکتور گرفتن و حذف کردن اطلاعات مرتبط خودداری کنید. پاسخ شما باید کامل و بی نقص باشد
* جداولی که در قالب markdown ارسال میشود را در پاسخ به صورت جداول html ارسال کن.
* به هیچ وجه جداول را به صورت markdown ارسال نکن.
* آدرس لینک هایی که داخل markdown قرار داده شده را در پاسخ به صورت تگ a با href برابر با آدرس آن لینک قرار دهید. همچنین target="__blank" تا در صفحه ی دیگری لینک باز شود.
* در پاسخ \n هایی که داخل سند قرار داده شده است را حذف نکنید.برای زیبایی پاسخ \n ها را باقی بگذارید.
* اطلاعات ارائه شده در قسمت Workflows را بر اطلاعات ارائه شده در قسمت Context Information: مقدم بدانید.

    @example:
        Context Information:
        سرویس لاله یک ماهه

        | نام سرویس | زمان  |  سرعت   | گیگ بین‌الملل | قیمت (تومان) |
        |---------------|---------------|---------|--------|------------|
        |   لاله یک   | 1 ماه |   تا 20 |        65     |     134.000   |

        User Question:
        شرایط سرویس های اینترنت به چه صورتی است ؟

        Assistant Response:
        <p>سرویس های اینترنتی ما به صورت زیر است:</p>
        <table>
            <tr>
                <th>نام سرویس</th>
                <th>زمان</th>
                <th>سرعت</th>
                <th>گیگ بین الملل</th>
                <th>(تومان) قیمت</th>
            </tr>
            <tr>
                <td>لاله یک</td>
                <td>1 ماه</td>
                <td>20</td>
                <td>65</td>
                <td>134.000</td>
            </tr>
        </table>  
        
    @example
        Context Information:
        برای مشاهده نمایندگی های شرکت ساتیا بر روی این <https://satia.co/agencies> کلیک کنید

        User Question:
        نمایندگی های ساتیا؟

        Assistant Response:
        برای مشاهده نمایندگی های شرکت ساتیا بر روی این <a href="https://satia.co/agencies">لینک</a> کلیک کنید.
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

    async def get_relevant_docs(self, question: str) -> List[Dict]:
        """
        Takes a user question and returns a list of relevant documents.
        
        Args:
            question (str): The user's question
            
        Returns:
            List[Dict]: List of relevant documents with their metadata and content
        """
        try:
            main_logger.info(f"Finding relevant documents for question: {question}")
            
            # Search for relevant documents
            relevant_docs = self.vector_store.search(question)

            # Log the titles of relevant documents
            if relevant_docs:
                titles = [doc['metadata'].get('title', 'Untitled') for doc in relevant_docs]
                main_logger.info(f"Relevant document founded in vector titles: {', '.join(titles)}")
            else:
                main_logger.info("No relevant documents found in vector")

            main_logger.debug(f"Found {len(relevant_docs)} relevant documents")
            
            # Create a document title analyzer agent
            title_analyzer = TitleAnalyzerAgent()
            
            # Prepare the input for the agent
            titles_info = "\n".join([
                f"ID: {doc['id']} - Title: {doc['metadata'].get('title', 'Untitled')}"
                for doc in relevant_docs
            ])
            
            agent_input = f"""User Question: {question}

            Available Documents:
            {titles_info}

            Please return only the IDs of the documents that are most relevant to answering the question, as a comma-separated list."""
            
            # Get the agent's response
            result = await Runner.run(title_analyzer, input=agent_input)
            
            # Parse the response to get the IDs
            selected_ids = [id.strip() for id in result.final_output.split(',')]
            
            # Filter and return the relevant documents
            filtered_docs = [
                doc for doc in relevant_docs 
                if doc['id'] in selected_ids
            ]

            # Log the titles of filtered documents
            if filtered_docs:
                filtered_titles = [doc['metadata'].get('title', 'Untitled') for doc in filtered_docs]
                main_logger.info(f"Selected documents after filtering with AI: {', '.join(filtered_titles)}")
            else:
                main_logger.info("No documents remained after filtering with AI")
            
            return filtered_docs
            
        except Exception as e:
            error_context = f"Question: {question}"
            log_error(error_logger, e, error_context)
            raise 

    async def generate_response_socket(self):
        try:
            main_logger.info(f"Generating response for question: {self.question}")

            # Search for relevant documents
            relevant_docs = await self.get_relevant_docs(self.question)
            print(f"Found {len(relevant_docs)} relevant documents", flush=True)
            
            # Sort documents by score
            relevant_docs = sorted(relevant_docs, key=lambda x: x.get('score', 1.0))
            
            # Format context with scores
            context_parts = []
            for doc in relevant_docs:
                score = doc.get('score', 1.0)
                text = doc['text']
                context_parts.append(f"[Score: {score:.3f}]\n{text}")
            
            context = "\n\n---\n\n".join(context_parts)
            
            # Format chat history if provided
            history_text = ""
            if self.history:
                history_parts = []
                for msg in self.history:
                    if isinstance(msg, str):
                        # If it's a string, try to parse it as JSON
                        try:
                            msg = json.loads(msg)
                        except json.JSONDecodeError:
                            # If it's not valid JSON, treat it as a regular message
                            history_parts.append(f"User: {msg}")
                            continue
                    
                    if isinstance(msg, dict) and msg.get('type'):
                        history_parts.append(json.dumps(msg))
                    else:
                        role = msg.get('role', 'user')
                        content = msg.get('body', '')
                        history_parts.append(f"{role.capitalize()}: {content}")
                history_text = "\n\nPrevious Conversation:\n" + "\n".join(history_parts)
            
            workflows_text = f"# Workflows\n\n{self.workflows}\n" if self.workflows else ""
            
            # Get active instructions from database
            active_instructions = self._get_active_instructions()
            
            full_input = f"""# Instructions

            {SATIA_INSTRUCTIONS}

            {active_instructions}

            # {workflows_text}

            Context Information:
            {context}

            {history_text}

            User Question: {self.question}"""
            
            # In your async function:
            stream = await to_thread.run_sync(self.stream_openai_response, full_input)

            print("Send response in socket ...", flush=True)
            
            full_response = ""
            
            # Send events to the client as they are received from OpenAI
            for event in stream:
                # Handle function call events
                if hasattr(event, 'item') and hasattr(event.item, 'name'):
                    print(f"Function called: {event.item.name}")
                    self.called_function = {
                        "type": "function_call",
                        "id" : event.item.id,
                        "call_id": event.item.id,
                        "name": event.item.name,
                        "arguments": event.item.arguments,
                    }
                    print(f"Arguments: {event.item.arguments}")
                
                # Handle function call arguments delta
                if event.type == 'response.function_call_arguments.delta':
                    print(f"Function arguments delta: {event.delta}")
                
                # Handle function call arguments done
                if event.type == 'response.function_call_arguments.done':
                    print(f"Function arguments completed: {event.arguments}")
                    self.called_function['arguments'] = event.arguments
                    break;
                
                # Handle regular text output
                if event.type == 'response.output_text.delta':
                    delta = event.delta
                    full_response += delta
                    await self.websocket.send_text(delta)
                    delay = str(os.getenv('GPT_RESPONSE_STREAM_SLEEP_SECOND', "0.0001"))
                    await asyncio.sleep(float(delay))
                    
            if self.called_function['name'] is not None:
                # If a function was called, handle it and get the new response
                await self.suplly_called_function()
                return full_response
            else:
                return full_response
            
        except Exception as e:
            error_context = f"Question: {self.question}"
            log_error(error_logger, e, error_context)
            raise
        
    def suplly_called_function(self):
        try:
            # Add function call to history
            self.history.append(self.called_function)
            
            # Call the function and get result
            result = call_function(self.called_function['name'], json.loads(self.called_function['arguments']))
            
            # Add result to chat history
            if self.history is None:
                self.history = []
            
            self.history.append({
                "type": "function_call_output",
                "call_id": self.called_function['call_id'],
                "output": json.dumps(result)
            })
            
        except Exception as e:
            error_logger.error(f"Error in supply_called_function: {str(e)}")
            
            # Add error information to chat history
            if self.history is None:
                self.history = []
            
            error_info = {
                "status": "error",
                "function": self.called_function['name'],
                "error": str(e)
            }
            
            self.history.append({
                "type": "function_call_output",
                "call_id": self.called_function['call_id'],
                "output": json.dumps(error_info)
            })
            
        finally:
            # Reset called_function regardless of success or failure
            self.called_function = {
                "name": None,
                "arguments": []
            }
            # Re-call generate_response_socket with updated history
            return asyncio.create_task(self.generate_response_socket())

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

    def stream_openai_response(self, full_input):
        """Stream response from OpenAI with tools configuration"""
        try:
            tools = self._load_tools_configuration()
            return self.client.responses.create(
               model=os.getenv("GPT_MODEL"),
               input=[
                   {"role": "developer", "content": full_input},
               ],
               stream=True,
               tools=tools
            )
        except Exception as e:
            error_logger.error(f"Error in stream_openai_response: {str(e)}")
            raise