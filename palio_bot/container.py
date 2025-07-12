"""Simple dependency container for the palio bot application."""

from typing import Dict, Optional

from .agent import Agent
from .system import System
from .text_editor_tool import create_text_editor_tools
from .llm_clients.llamacpp_client import LlamaCPPClient
from .models import Tool


class Container:
    """Simple dependency container for the application."""

    def __init__(self, palio_file_path: str = "palio.json", llamacpp_url: str = "http://mac-studio.local:11454"):
        """Initialize the container with configuration."""
        self.palio_file_path = palio_file_path
        self.llamacpp_url = llamacpp_url

        # Initialize all services lazily
        self._llm_client: Optional[LlamaCPPClient] = None
        self._tools: Optional[Dict[str, Tool]] = None
        self._agent: Optional[Agent] = None
        self._system: Optional[System] = None

    def llm_client(self) -> LlamaCPPClient:
        """Get or create LLM client."""
        if self._llm_client is None:
            self._llm_client = LlamaCPPClient(base_url=self.llamacpp_url)
        return self._llm_client

    def tools(self) -> Dict[str, Tool]:
        """Get or create tools."""
        if self._tools is None:
            self._tools = create_text_editor_tools(file_path=self.palio_file_path)
        return self._tools

    def agent(self) -> Agent:
        """Get or create agent."""
        if self._agent is None:
            self._agent = Agent(
                llm_client=self.llm_client(),
                tools=self.tools()
            )
        return self._agent

    def system(self) -> System:
        """Get or create system."""
        if self._system is None:
            self._system = System(
                agent=self.agent(),
                palio_file_path=self.palio_file_path,
                session_file_path="session.json"
            )
        return self._system

    async def init_container(self) -> None:
        """Initialize the container by creating all services."""
        # Initialize all services to ensure they're created
        self.llm_client()
        self.tools()
        self.agent()
        self.system()
        
        # All initialization is done during service creation
        # No additional setup needed for this simple system