from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class HTMLToMarkdownAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def convert(self, html_content: str) -> str:
        """
        Convert HTML content to Markdown using OpenAI.
        Returns the markdown content if successful, None if failed.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",  # or any other suitable model
                messages=[
                    {
                        "role": "system",
                        "content": "You are a specialized HTML to Markdown converter. Convert the given HTML content to clean, well-formatted Markdown. Preserve all important information, links, and structure."
                    },
                    {
                        "role": "user",
                        "content": f"Convert this HTML to Markdown:\n\n{html_content}"
                    }
                ],
                temperature=0.1  # Low temperature for consistent output
            )
            
            markdown = response.choices[0].message.content
            return markdown
        except Exception as e:
            print(f"Error converting HTML to Markdown: {str(e)}")
            return None 