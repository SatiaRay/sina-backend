import os
from agents import Agent

class TitleAnalyzerAgent(Agent):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TitleAnalyzerAgent, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, '_initialized'):
            super().__init__(
                name="Document Title Analyzer",
                instructions="""
                Analyze the given question and document titles to determine which documents are most relevant.
                Return only the IDs of the documents that are most relevant to answering the question.
                Format your response as a comma-separated list of document IDs.
                """,
                model=os.getenv("GPT_TITLE_ANALYZER_MODEL")
            )
            self._initialized = True