from agents import Agent, Runner
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
from database.vector_store import VectorStore
from models.agents.title_analyzer_agent import TitleAnalyzerAgent
from models.text_processor import TextProcessor
import logging
from util.logging_config import configure_logging, log_error
import asyncio
from fastapi import WebSocket
from openai import OpenAI
from anyio import to_thread
from .chat_agent_rag_interface import ChatAgentRagInterface

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
    def __init__(self):
        self.vector_store = VectorStore()

        self.client = OpenAI()
        
        main_logger.info("Initialized Agent RAG System with GPT-4")


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

    async def generate_response_socket(self, question: str, websocket: WebSocket, history: Optional[List[Dict[str, str]]] = None, workflows: Optional[str] = None):
        try:
            main_logger.info(f"Generating response for question: {question}")

            # Search for relevant documents
            relevant_docs = await self.get_relevant_docs(question)
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
            if history:
                history_parts = []
                for msg in history:
                    role = msg.get('role', 'user')
                    content = msg.get('body', '')
                    history_parts.append(f"{role.capitalize()}: {content}")
                history_text = "\n\nPrevious Conversation:\n" + "\n".join(history_parts)
            
            # Combine question, context, and history
            full_input = f"""
            # Instructions

            {SATIA_INSTRUCTIONS}
            
            {f'# Workflows\n\n{workflows}\n' if workflows else ''}
            
            Context Information:
            {context}
            
            {history_text}
            
            User Question: {question}"""

            print(full_input)

            # In your async function:
            stream = await to_thread.run_sync(self.stream_openai_response, full_input)

            print("Send response in socket ...", flush=True)

            full_response = ""
            
            # Send events to the client as they are received from OpenAI
            for event in stream:
                if event.type == 'response.output_text.delta':
                    delta = event.delta
                    full_response += delta
                    await websocket.send_text(delta)
                    delay = str(os.getenv('GPT_RESPONSE_STREAM_SLEEP_SECOND', "0.0001"))
                    await asyncio.sleep(float(delay))

            return full_response
            
        except Exception as e:
            error_context = f"Question: {question}"
            log_error(error_logger, e, error_context)
            raise


    def stream_openai_response(self, full_input):
        return self.client.responses.create(
           model=os.getenv("GPT_MODEL"),
           input=[
               {"role": "developer", "content": full_input},
           ],
           stream=True,
        )