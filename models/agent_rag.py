from agents import Agent, Runner
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from database.vector_store import VectorStore
from models.text_processor import TextProcessor
import logging
from util.logging_config import configure_logging, log_error
import asyncio

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
* وقتی سندی را در قالب html برای شما ارسال میکنم, در ساختن پاسخ به تگ های html توجه داشته باشید. برای مثال وقتی اطلاعاتی به صورت جدول و تگ <table> قرار داده شده, در پاسخ هم از همان قالب استفاده کن. یا لیست ها <ul> و <li> و ...

    @example:
        Context Information:
        <table>
            <tr>
                <th>نام سرویس</th>
                <th>سرعت</th>
                <th>قیمت</th>
            </tr>
            <tr>
                <td>سرویس 1</td>
                <td>100 Mbps</td>
                <td>100,000 تومان</td>
            </tr>
        </table>

        User Question:
        شرایط سرویس های اینترنت به چه صورتی است ؟

        Assistant Response:
        <p>سرویس های اینترنتی ما به صورت زیر است:</p>
        <table>
            <tr>
                <th>نام سرویس</th>
                <th>سرعت</th>
                <th>قیمت</th>
            </tr>
            <tr>
                <td>سرویس 1</td>
                <td>100 Mbps</td>
                <td>100,000 تومان</td>
            </tr>
        </table>  
        

        

* از فاکتور گرفتن و حذف کردن اطلاعات مرتبط خودداری کنید. پاسخ شما باید کامل و بی نقص باشد

"""

class AgentRAGSystem:
    def __init__(self):
        self.vector_store = VectorStore()
        self.text_processor = TextProcessor()
        
        # Create the main Satia support agent
        self.persian_agent = Agent(
            name="Satia Persian Support",
            instructions=SATIA_INSTRUCTIONS,
            model=os.getenv("GPT_MODEL"),  # Using model from environment variable
        )
        
        # Create an English support agent
        self.english_agent = Agent(
            name="Satia English Support",
            instructions=SATIA_INSTRUCTIONS.replace("به زبان فارسی", "in English"),
            model=os.getenv("GPT_MODEL"),
        )
        
        # Create a triage agent to handle language selection
        self.triage_agent = Agent(
            name="Language Triage",
            instructions="""
            Determine the language of the user's question and hand off to the appropriate agent:
            - For Persian/Farsi questions -> Persian Support Agent
            - For English questions -> English Support Agent
            Always prioritize Persian if the question contains both languages.
            """,
            handoffs=[self.persian_agent, self.english_agent],
            model=os.getenv("GPT_MODEL"),
        )
        
        main_logger.info("Initialized Agent RAG System with GPT-4")

    

    async def generate_response(self, question: str) -> Dict[str, Any]:
        try:
            main_logger.info(f"Generating response for question: {question}")
            
            # Search for relevant documents
            relevant_docs = await self.get_relevant_docs(question)
            main_logger.debug(f"Found {len(relevant_docs)} relevant documents")
            print(f"Found {len(relevant_docs)} relevant documents")
            
            # Sort documents by score
            relevant_docs = sorted(relevant_docs, key=lambda x: x.get('score', 1.0))
            
            # Format context with scores
            context_parts = []
            for doc in relevant_docs:
                score = doc.get('score', 1.0)
                text = doc['text']
                context_parts.append(f"[Score: {score:.3f}]\n{text}")
            
            context = "\n\n---\n\n".join(context_parts)
            
            # Combine question and context
            full_input = f"""Context Information:
            {context}
            
            User Question: {question}"""
            
            # Run through the agent system
            result = await Runner.run(self.triage_agent, input=full_input)
            
            return {
                'answer': result.final_output,
                'sources': [
                    {
                        'text': doc['text'],
                        'metadata': doc['metadata'],
                        'score': doc.get('score', 1.0)
                    }
                    for doc in relevant_docs
                ]
            }
            
        except Exception as e:
            error_context = f"Question: {question}"
            log_error(error_logger, e, error_context)
            raise

    async def update_knowledge_base(self, url_or_documents):
        """Keeps the same knowledge base update functionality"""
        # Reuse the existing update_knowledge_base logic
        pass  # We'll implement this later if needed 

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
            main_logger.debug(f"Found {len(relevant_docs)} relevant documents")
            
            # Create a document title analyzer agent
            title_analyzer = Agent(
                name="Document Title Analyzer",
                instructions="""
                Analyze the given question and document titles to determine which documents are most relevant.
                Return only the IDs of the documents that are most relevant to answering the question.
                Format your response as a comma-separated list of document IDs.
                """,
                model=os.getenv("GPT_MODEL")
            )
            
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
            
            return filtered_docs
            
        except Exception as e:
            error_context = f"Question: {question}"
            log_error(error_logger, e, error_context)
            raise 