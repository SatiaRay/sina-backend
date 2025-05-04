import os
from agents import Agent, Runner
import asyncio

# Instructions for the HTML to Markdown conversion agent
HTML_TO_MARKDOWN_INSTRUCTIONS = """
# Identity

You are a specialized HTML to Markdown converter. Your task is to convert HTML content into clean, well-formatted Markdown while preserving:

# Instructions

1. All important information and structure
2. Links and their text
3. Headings and their hierarchy
4. Lists (ordered and unordered)
5. Tables and their structure
6. Code blocks and inline code
7. Blockquotes and emphasis

Convert the HTML content while maintaining readability and proper Markdown syntax.

# Examples

<user_query>
    <table class="table">
        <thead>
            <tr style="background-color: #DF2829;">
                <th style="border-radius: 0px 10px 0px 0px;">Service Name</th>
                <th>Time</th>
                <th>Speed (Mbps)</th>
                <th>Gigs</th>
                <th style="border-radius: 10px 0px 0px 0px;">Price</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="text-align:center">Laleh 1</td>
                <td>Monthly</td>
                <td>Up to 20 Mbps</td>
                <td>65</td>
                <td style="border-left:none !important">134,000</td>
            </tr>
        </tbody>
    </table>
</user_query>

<assistant_response>
    | Service Name |   Time   |  Speed (Mbps) | Gigs |  Price  |
    |--------------|----------|---------------|------|---------|
    | Laleh 1      |  Monthly | Up to 20 Mbps |  65  | 134,000 |
</assistant_response>
"""

class HTMLToMarkdownAgent:
    def __init__(self):
        self.agent = Agent(
            name="HTML to Markdown Converter",
            instructions=HTML_TO_MARKDOWN_INSTRUCTIONS,
            model=os.getenv("GPT_MODEL", "gpt-4"),  # Default to gpt-4 if not specified
        )
        
    async def convert(self, html_content: str) -> str:
        """
        Convert HTML content to Markdown using the agent.
        Returns the markdown content if successful, None if failed.
        """
        print(f"Converting HTML to Markdown:\n\n{html_content}")
        try:
            result = await Runner.run(self.agent, input=f"Convert this HTML to Markdown:\n\n{html_content}")
            return str(result.final_output)
        except Exception as e:
            print(f"Error converting HTML to Markdown: {str(e)}")
            return None 